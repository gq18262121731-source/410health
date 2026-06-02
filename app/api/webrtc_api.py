from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_runtime
from app.core.runtime import Runtime
from app.schemas.webrtc import AckResponse, IceCandidateRequest, WebRTCOfferRequest, WebRTCOfferResponse

router = APIRouter(tags=["webrtc"])


@router.post("/webrtc/offer", response_model=WebRTCOfferResponse)
async def webrtc_offer(
    request: WebRTCOfferRequest,
    runtime: Runtime = Depends(get_runtime),
) -> WebRTCOfferResponse:
    try:
        peer_id, sdp, type_ = await runtime.peer_manager.handle_offer(
            camera_id=request.camera_id,
            sdp=request.sdp,
            type_=request.type,
            prefer_latest_frame=request.prefer_latest_frame,
            preferred_display_source=request.preferred_display_source,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return WebRTCOfferResponse(peer_id=peer_id, sdp=sdp, type=type_)


@router.post("/webrtc/candidate", response_model=AckResponse)
async def webrtc_candidate(request: IceCandidateRequest) -> AckResponse:
    return AckResponse(ok=True, message="trickle ICE is reserved for a later phase")
