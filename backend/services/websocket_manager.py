from __future__ import annotations

import asyncio
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from fastapi import WebSocket


@dataclass(slots=True)
class AlarmSubscription:
    websocket: WebSocket
    allowed_macs: set[str] | None = None


class WebSocketManager:
    """In-memory websocket registry for health streams and alarms."""

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

    async def connect_alarm(self, websocket: WebSocket, *, allowed_macs: set[str] | None = None) -> None:
        await websocket.accept()
        async with self._lock:
            self._alarm_channels[websocket] = AlarmSubscription(
                websocket=websocket,
                allowed_macs={self._normalize_mac(mac) for mac in allowed_macs} if allowed_macs is not None else None,
            )

    async def disconnect_alarm(self, websocket: WebSocket) -> None:
        async with self._lock:
            self._alarm_channels.pop(websocket, None)

    async def broadcast_health(self, device_mac: str, payload: dict[str, Any]) -> None:
        normalized = self._normalize_mac(device_mac)
        sockets = list(self._health_channels.get(normalized, set()))
        results = await asyncio.gather(
            *(self._send_json(socket, payload) for socket in sockets),
            return_exceptions=True,
        )
        for socket, result in zip(sockets, results, strict=False):
            if isinstance(result, Exception):
                await self.disconnect_health(device_mac, socket)

    async def broadcast_alarm(self, payload: dict[str, Any]) -> None:
        subscriptions = list(self._alarm_channels.values())
        targets = [
            subscription.websocket
            for subscription in subscriptions
            if self._subscription_accepts_alarm(subscription, payload)
        ]
        results = await asyncio.gather(
            *(self._send_json(socket, payload) for socket in targets),
            return_exceptions=True,
        )
        for socket, result in zip(targets, results, strict=False):
            if isinstance(result, Exception):
                await self.disconnect_alarm(socket)

    async def broadcast_alarm_queue(self, payload: dict[str, Any]) -> None:
        subscriptions = list(self._alarm_channels.values())
        results = await asyncio.gather(
            *(
                self._send_json(subscription.websocket, self._filter_alarm_queue_payload(payload, subscription))
                for subscription in subscriptions
            ),
            return_exceptions=True,
        )
        for subscription, result in zip(subscriptions, results, strict=False):
            if isinstance(result, Exception):
                await self.disconnect_alarm(subscription.websocket)

    async def _send_json(self, websocket: WebSocket, payload: dict[str, Any]) -> None:
        await websocket.send_json(payload)

    def _subscription_accepts_alarm(self, subscription: AlarmSubscription, payload: dict[str, Any]) -> bool:
        if subscription.allowed_macs is None:
            return True
        device_mac = str(payload.get("device_mac", "")).strip()
        if not device_mac:
            return False
        return self._normalize_mac(device_mac) in subscription.allowed_macs

    def _filter_alarm_queue_payload(
        self,
        payload: dict[str, Any],
        subscription: AlarmSubscription,
    ) -> dict[str, Any]:
        if subscription.allowed_macs is None:
            return payload

        queue = payload.get("queue", [])
        if not isinstance(queue, list):
            return payload

        filtered_queue = [
            item
            for item in queue
            if self._queue_item_matches_subscription(item, subscription)
        ]
        snapshot = dict(payload.get("snapshot", {})) if isinstance(payload.get("snapshot"), dict) else {}
        snapshot["length"] = len(filtered_queue)
        snapshot["head"] = [
            self._queue_item_alarm_id(item)
            for item in filtered_queue[:5]
            if self._queue_item_alarm_id(item)
        ]
        return {
            **payload,
            "queue": filtered_queue,
            "snapshot": snapshot,
        }

    def _queue_item_matches_subscription(self, item: Any, subscription: AlarmSubscription) -> bool:
        if subscription.allowed_macs is None:
            return True
        if not isinstance(item, dict):
            return False
        alarm = item.get("alarm", item)
        if not isinstance(alarm, dict):
            return False
        device_mac = str(alarm.get("device_mac", "")).strip()
        if not device_mac:
            return False
        return self._normalize_mac(device_mac) in subscription.allowed_macs

    @staticmethod
    def _queue_item_alarm_id(item: Any) -> str:
        if not isinstance(item, dict):
            return ""
        alarm = item.get("alarm", item)
        if not isinstance(alarm, dict):
            return ""
        return str(alarm.get("id", "")).strip()
