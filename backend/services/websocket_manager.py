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
    visible_family_ids: set[str] | None = None
    visible_elder_ids: set[str] | None = None


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
        visible_family_ids: set[str] | None = None,
        visible_elder_ids: set[str] | None = None,
    ) -> None:
        await websocket.accept()
        async with self._lock:
            normalized_macs = {
                self._normalize_mac(device_mac)
                for device_mac in (visible_device_macs or set())
                if device_mac
            }
            normalized_family_ids = {
                str(family_id).strip()
                for family_id in (visible_family_ids or set())
                if str(family_id).strip()
            }
            normalized_elder_ids = {
                str(elder_id).strip()
                for elder_id in (visible_elder_ids or set())
                if str(elder_id).strip()
            }
            self._alarm_channels[websocket] = AlarmSubscription(
                websocket=websocket,
                allow_all=allow_all,
                visible_device_macs=normalized_macs,
                visible_family_ids=normalized_family_ids,
                visible_elder_ids=normalized_elder_ids,
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
        visible_family_ids: set[str] | None = None,
        visible_elder_ids: set[str] | None = None,
    ) -> dict[str, Any] | None:
        normalized_macs = {
            self._normalize_mac(device_mac)
            for device_mac in (visible_device_macs or set())
            if device_mac
        }
        normalized_family_ids = {
            str(family_id).strip()
            for family_id in (visible_family_ids or set())
            if str(family_id).strip()
        }
        normalized_elder_ids = {
            str(elder_id).strip()
            for elder_id in (visible_elder_ids or set())
            if str(elder_id).strip()
        }
        return self._scope_alarm_payload(
            AlarmSubscription(
                websocket=None,  # type: ignore[arg-type]
                allow_all=allow_all,
                visible_device_macs=normalized_macs,
                visible_family_ids=normalized_family_ids,
                visible_elder_ids=normalized_elder_ids,
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
        visible_family_ids = subscription.visible_family_ids or set()
        visible_elder_ids = subscription.visible_elder_ids or set()
        has_scope = bool(visible_device_macs or visible_family_ids or visible_elder_ids)
        if not has_scope:
            return payload if payload.get("type") == "alarm_queue" else None

        if payload.get("type") == "alarm_queue":
            raw_queue = payload.get("queue")
            if not isinstance(raw_queue, list):
                return payload
            filtered_queue = [
                item
                for item in raw_queue
                if self._queue_item_visible(
                    item,
                    visible_device_macs=visible_device_macs,
                    visible_family_ids=visible_family_ids,
                    visible_elder_ids=visible_elder_ids,
                )
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

        if self._alarm_payload_visible(
            payload,
            visible_device_macs=visible_device_macs,
            visible_family_ids=visible_family_ids,
            visible_elder_ids=visible_elder_ids,
        ):
            return payload
        return None

    def _queue_item_visible(
        self,
        item: Any,
        *,
        visible_device_macs: set[str],
        visible_family_ids: set[str],
        visible_elder_ids: set[str],
    ) -> bool:
        if not isinstance(item, dict):
            return False
        alarm = item.get("alarm")
        if not isinstance(alarm, dict):
            return False
        return self._alarm_payload_visible(
            alarm,
            visible_device_macs=visible_device_macs,
            visible_family_ids=visible_family_ids,
            visible_elder_ids=visible_elder_ids,
        )

    def _alarm_payload_visible(
        self,
        payload: dict[str, Any],
        *,
        visible_device_macs: set[str],
        visible_family_ids: set[str],
        visible_elder_ids: set[str],
    ) -> bool:
        device_mac = payload.get("device_mac")
        if isinstance(device_mac, str) and self._normalize_mac(device_mac) in visible_device_macs:
            return True

        metadata = payload.get("metadata")
        if not isinstance(metadata, dict):
            return False

        elder_id = metadata.get("elder_id")
        if isinstance(elder_id, str) and elder_id.strip() and elder_id.strip() in visible_elder_ids:
            return True

        family_ids = metadata.get("family_ids")
        if isinstance(family_ids, list):
            for family_id in family_ids:
                normalized = str(family_id).strip()
                if normalized and normalized in visible_family_ids:
                    return True

        event = metadata.get("event")
        if isinstance(event, dict):
            event_elder_id = event.get("elder_id")
            if isinstance(event_elder_id, str) and event_elder_id.strip() and event_elder_id.strip() in visible_elder_ids:
                return True

        return False

    async def _send_many(self, sockets: list[WebSocket], payload: dict[str, Any]) -> list[WebSocket]:
        async def send(socket: WebSocket) -> WebSocket | None:
            try:
                await asyncio.wait_for(socket.send_json(payload), timeout=0.2)
                return None
            except Exception:
                return socket

        results = await asyncio.gather(*(send(socket) for socket in sockets), return_exceptions=False)
        return [socket for socket in results if socket is not None]
