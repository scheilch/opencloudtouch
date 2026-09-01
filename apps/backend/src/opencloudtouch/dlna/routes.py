"""DLNA API routes."""

from dataclasses import asdict

from fastapi import APIRouter, HTTPException, Query, Request

from opencloudtouch.dlna.client import DlnaBrowseError
from opencloudtouch.dlna.playback import DlnaPlaybackError
from opencloudtouch.dlna.renderer import DlnaRendererError
from opencloudtouch.dlna.service import DlnaService

router = APIRouter(prefix="/api/dlna", tags=["dlna"])

_service = DlnaService()


async def _get_device_ip(request: Request, device_id: str) -> str:
    """Resolve a SoundTouch device IP through the OCT DeviceService."""
    device_service = request.app.state.device_service
    device = await device_service.get_device_by_id(device_id)

    if device is None:
        raise HTTPException(
            status_code=404,
            detail=f"Device not found: {device_id}",
        )

    return device.ip


@router.get("/servers")
async def get_dlna_servers() -> list[dict]:
    """Discover DLNA media servers."""
    servers = await _service.get_servers()
    return [asdict(server) for server in servers]


@router.get("/servers/{server_id}/browse")
async def browse_dlna_server(
    server_id: str,
    object_id: str = Query(default="0"),
) -> dict:
    """Browse a DLNA MediaServer ContentDirectory."""
    try:
        items = await _service.browse(server_id, object_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except DlnaBrowseError as exc:
        if exc.error_code == "701":
            raise HTTPException(
                status_code=404,
                detail=f"DLNA object not found: {object_id}",
            ) from exc

        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return {
        "server_id": server_id,
        "object_id": object_id,
        "items": [asdict(item) for item in items],
    }


@router.post("/servers/{server_id}/items/{object_id}/play/{device_id}")
async def play_dlna_item(
    request: Request,
    server_id: str,
    object_id: str,
    device_id: str,
    parent_id: str = Query(...),
) -> dict:
    """Play a DLNA item on a SoundTouch device."""
    device_ip = await _get_device_ip(request, device_id)

    try:
        item = await _service.play(
            device_id=device_id,
            device_ip=device_ip,
            server_id=server_id,
            parent_id=parent_id,
            object_id=object_id,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except DlnaPlaybackError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (DlnaBrowseError, DlnaRendererError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return {
        "device_id": device_id,
        "item": asdict(item),
    }


@router.post("/devices/{device_id}/pause")
async def pause_dlna(
    request: Request,
    device_id: str,
) -> dict:
    """Pause current DLNA playback."""
    device_ip = await _get_device_ip(request, device_id)

    try:
        await _service.pause(device_id, device_ip)
    except DlnaPlaybackError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except DlnaRendererError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return {"device_id": device_id, "status": "paused"}


@router.post("/devices/{device_id}/resume")
async def resume_dlna(
    request: Request,
    device_id: str,
) -> dict:
    """Resume current DLNA playback."""
    device_ip = await _get_device_ip(request, device_id)

    try:
        await _service.resume(device_id, device_ip)
    except DlnaPlaybackError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except DlnaRendererError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return {"device_id": device_id, "status": "playing"}


@router.post("/devices/{device_id}/next")
async def next_dlna(
    request: Request,
    device_id: str,
) -> dict:
    """Play the next DLNA track."""
    device_ip = await _get_device_ip(request, device_id)

    try:
        item = await _service.next(device_id, device_ip)
    except DlnaPlaybackError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except DlnaRendererError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return {
        "device_id": device_id,
        "item": asdict(item),
    }


@router.post("/devices/{device_id}/previous")
async def previous_dlna(
    request: Request,
    device_id: str,
) -> dict:
    """Play the previous DLNA track."""
    device_ip = await _get_device_ip(request, device_id)

    try:
        item = await _service.previous(device_id, device_ip)
    except DlnaPlaybackError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except DlnaRendererError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return {
        "device_id": device_id,
        "item": asdict(item),
    }
