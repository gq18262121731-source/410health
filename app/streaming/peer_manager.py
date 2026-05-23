from __future__ import annotations

import uuid

from aiortc import RTCConfiguration, RTCIceServer, RTCPeerConnection, RTCSessionDescription

from app.camera.source_manager import CameraSourceManager
from app.core.config import Settings
from app.core.logger import get_logger
from app.streaming.media_track import LatestFrameVideoTrack

logger = get_logger(__name__)


class PeerManager:
    def __init__(self, settings: Settings, source_manager: CameraSourceManager) -> None:
        self.settings = settings
        self.source_manager = source_manager
        self._peers: dict[str, RTCPeerConnection] = {}

    @property
    def client_count(self) -> int:
        return len(self._peers)

    async def handle_offer(self, camera_id: str, sdp: str, type_: str) -> tuple[str, str, str]:
        runtime = self.source_manager.get_runtime(camera_id)
        if runtime is None:
            raise ValueError(f"camera {camera_id} is not running")

        peer_id = uuid.uuid4().hex
        pc = RTCPeerConnection(
            configuration=RTCConfiguration(
                iceServers=[RTCIceServer(urls=[self.settings.webrtc_stun_server])]
            )
        )
        self._peers[peer_id] = pc

        @pc.on("connectionstatechange")
        async def on_connectionstatechange() -> None:
            logger.info(
                "peer_connection_state peer_id=%s state=%s",
                peer_id,
                pc.connectionState,
            )
            if pc.connectionState in {"failed", "closed", "disconnected"}:
                await self.close(peer_id)

        track = LatestFrameVideoTrack(runtime.frame_buffer, self.settings).track
        pc.addTrack(track)

        offer = RTCSessionDescription(sdp=sdp, type=type_)
        await pc.setRemoteDescription(offer)
        answer = await pc.createAnswer()
        await pc.setLocalDescription(answer)
        logger.info("peer_created peer_id=%s camera_id=%s", peer_id, camera_id)
        return peer_id, pc.localDescription.sdp, pc.localDescription.type

    async def close(self, peer_id: str) -> None:
        pc = self._peers.pop(peer_id, None)
        if pc:
            await pc.close()
            logger.info("peer_closed peer_id=%s", peer_id)

    async def close_all(self) -> None:
        for peer_id in list(self._peers.keys()):
            await self.close(peer_id)

