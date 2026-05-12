from __future__ import annotations

import asyncio
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from fastapi import WebSocket


@dataclass(slots=True)
class AlarmSubscription:
    websocket: WebSocket
    allow_all: bool = True
    visible_device_macs: set[str] | None = None


class WebSocketManager:
    """Simple in-memory websocket registry for health streams and alarms."""

    @staticmethod
    def _normalize_mac(device_mac: str) -> str:
        compact = "".join(ch for ch in device_mac if ch.isalnum()).upper()
        if len(compact) == 12:
            return ":".join(compact[i : i + 2] for i in range(0, 12, 2))
        return device_mac.upper()

    def __init__(self) -> None:
        self._health_channels: dict[str, set[WebSocket]] = defaultdict(set)
        self._alarm_channels: dict[WebSocket, AlarmSubscription] = {}
        self._lock = asyncio.Lock()

    async def connect_health(self, device_mac: str, websocket: WebSocket) -> None:
        normalized = self._normalize_mac(device_mac)
        await websocket.accept()
        async with self._lock:
            self._health_channels[normalized].add(websocket)

    async def disconnect_health(self, device_mac: str, websocket: WebSocket) -> None:
        normalized = self._normalize_mac(device_mac)
        async with self._lock:
            self._health_channels[normalized].discard(websocket)

    async def connect_alarm(
        self,
        websocket: WebSocket,
        *,
        allow_all: bool = True,
        visible_device_macs: set[str] | None = None,
    ) -> None:
        await websocket.accept()
        async with self._lock:
            normalized_macs = {
                self._normalize_mac(device_mac)
                for device_mac in (visible_device_macs or set())
                if device_mac
            }
            self._alarm_channels[websocket] = AlarmSubscription(
                websocket=websocket,
                allow_all=allow_all,
                visible_device_macs=normalized_macs,
            )

    async def disconnect_alarm(self, websocket: WebSocket) -> None:
        async with self._lock:
            self._alarm_channels.pop(websocket, None)

    async def broadcast_health(self, device_mac: str, payload: dict[str, Any]) -> None:
        normalized = self._normalize_mac(device_mac)
        sockets = list(self._health_channels.get(normalized, set()))
        stale = await self._send_many(sockets, payload)
        for socket in stale:
            await self.disconnect_health(device_mac, socket)

    async def broadcast_alarm(self, payload: dict[str, Any]) -> None:
        subscriptions = list(self._alarm_channels.values())
        stale = await self._send_alarm_payload_many(subscriptions, payload)
        for socket in stale:
            await self.disconnect_alarm(socket)

    async def broadcast_alarm_queue(self, payload: dict[str, Any]) -> None:
        subscriptions = list(self._alarm_channels.values())
        stale = await self._send_alarm_payload_many(subscriptions, payload)
        for socket in stale:
            await self.disconnect_alarm(socket)

    async def _send_alarm_payload_many(
        self,
        subscriptions: list[AlarmSubscription],
        payload: dict[str, Any],
    ) -> list[WebSocket]:
        async def send(subscription: AlarmSubscription) -> WebSocket | None:
            try:
                scoped_payload = self._scope_alarm_payload(subscription, payload)
                if scoped_payload is None:
                    return None
                await asyncio.wait_for(subscription.websocket.send_json(scoped_payload), timeout=0.2)
                return None
            except Exception:
                return subscription.websocket

        results = await asyncio.gather(*(send(subscription) for subscription in subscriptions), return_exceptions=False)
        return [socket for socket in results if socket is not None]

    def scope_alarm_payload_for_viewer(
        self,
        payload: dict[str, Any],
        *,
        allow_all: bool,
        visible_device_macs: set[str] | None,
    ) -> dict[str, Any] | None:
        normalized_macs = {
            self._normalize_mac(device_mac)
            for device_mac in (visible_device_macs or set())
            if device_mac
        }
        return self._scope_alarm_payload(
            AlarmSubscription(
                websocket=None,  # type: ignore[arg-type]
                allow_all=allow_all,
                visible_device_macs=normalized_macs,
            ),
            payload,
        )

    def _scope_alarm_payload(
        self,
        subscription: AlarmSubscription,
        payload: dict[str, Any],
    ) -> dict[str, Any] | None:
        if subscription.allow_all:
            return payload

        visible_device_macs = subscription.visible_device_macs or set()
        if not visible_device_macs:
            return payload if payload.get("type") == "alarm_queue" else None

        if payload.get("type") == "alarm_queue":
            raw_queue = payload.get("queue")
            if not isinstance(raw_queue, list):
                return payload
            filtered_queue = [
                item
                for item in raw_queue
                if self._queue_item_visible(item, visible_device_macs)
            ]
            scoped_payload = dict(payload)
            scoped_payload["queue"] = filtered_queue
            snapshot = payload.get("snapshot")
            if isinstance(snapshot, dict):
                scoped_snapshot = dict(snapshot)
                scoped_snapshot["length"] = len(filtered_queue)
                scoped_snapshot["head"] = [
                    alarm_id
                    for alarm_id in (
                        item.get("alarm", {}).get("id")
                        if isinstance(item, dict) and isinstance(item.get("alarm"), dict)
                        else None
                        for item in filtered_queue
                    )
                    if alarm_id
                ][:5]
                scoped_payload["snapshot"] = scoped_snapshot
            return scoped_payload

        device_mac = payload.get("device_mac")
        if isinstance(device_mac, str) and self._normalize_mac(device_mac) in visible_device_macs:
            return payload
        return None

    def _queue_item_visible(self, item: Any, visible_device_macs: set[str]) -> bool:
        if not isinstance(item, dict):
            return False
        alarm = item.get("alarm")
        if not isinstance(alarm, dict):
            return False
        device_mac = alarm.get("device_mac")
        if not isinstance(device_mac, str):
            return False
        return self._normalize_mac(device_mac) in visible_device_macs

    async def _send_many(self, sockets: list[WebSocket], payload: dict[str, Any]) -> list[WebSocket]:
        async def send(socket: WebSocket) -> WebSocket | None:
            try:
                await asyncio.wait_for(socket.send_json(payload), timeout=0.2)
                return None
            except Exception:
                return socket

        results = await asyncio.gather(*(send(socket) for socket in sockets), return_exceptions=False)
        return [socket for socket in results if socket is not None]
