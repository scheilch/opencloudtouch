"""Tests for DLNA playback queue management."""

from unittest.mock import AsyncMock

import pytest

from opencloudtouch.dlna.models import DlnaItem
from opencloudtouch.dlna.playback import DlnaPlaybackError, DlnaPlaybackService


def make_track(track_id: str, url: str) -> DlnaItem:
    """Create a playable DLNA test item."""
    return DlnaItem(
        id=track_id,
        parent_id="1$4",
        title=track_id,
        is_container=False,
        resource_url=url,
        media_class="object.item.audioItem.musicTrack",
    )


@pytest.mark.asyncio
async def test_play_creates_queue():
    renderer = AsyncMock()
    service = DlnaPlaybackService(renderer=renderer)

    first = make_track("track-1", "http://server/1.mp3")
    second = make_track("track-2", "http://server/2.mp3")

    result = await service.play(
        device_id="device-1",
        device_ip="192.0.2.10",
        server_id="server-1",
        items=[first, second],
        object_id="track-1",
    )

    assert result == first
    renderer.play_uri.assert_awaited_once_with(
        "192.0.2.10",
        "http://server/1.mp3",
    )


@pytest.mark.asyncio
async def test_next_track():
    renderer = AsyncMock()
    service = DlnaPlaybackService(renderer=renderer)

    first = make_track("track-1", "http://server/1.mp3")
    second = make_track("track-2", "http://server/2.mp3")

    await service.play(
        "device-1",
        "192.0.2.10",
        "server-1",
        [first, second],
        "track-1",
    )

    renderer.reset_mock()

    result = await service.next("device-1", "192.0.2.10")

    assert result == second
    renderer.play_uri.assert_awaited_once_with(
        "192.0.2.10",
        "http://server/2.mp3",
    )


@pytest.mark.asyncio
async def test_previous_track():
    renderer = AsyncMock()
    service = DlnaPlaybackService(renderer=renderer)

    first = make_track("track-1", "http://server/1.mp3")
    second = make_track("track-2", "http://server/2.mp3")

    await service.play(
        "device-1",
        "192.0.2.10",
        "server-1",
        [first, second],
        "track-2",
    )

    renderer.reset_mock()

    result = await service.previous("device-1", "192.0.2.10")

    assert result == first


@pytest.mark.asyncio
async def test_next_at_end_fails():
    renderer = AsyncMock()
    service = DlnaPlaybackService(renderer=renderer)

    track = make_track("track-1", "http://server/1.mp3")

    await service.play(
        "device-1",
        "192.0.2.10",
        "server-1",
        [track],
        "track-1",
    )

    with pytest.raises(DlnaPlaybackError, match="No next"):
        await service.next("device-1", "192.0.2.10")


@pytest.mark.asyncio
async def test_previous_at_start_fails():
    renderer = AsyncMock()
    service = DlnaPlaybackService(renderer=renderer)

    track = make_track("track-1", "http://server/1.mp3")

    await service.play(
        "device-1",
        "192.0.2.10",
        "server-1",
        [track],
        "track-1",
    )

    with pytest.raises(DlnaPlaybackError, match="No previous"):
        await service.previous("device-1", "192.0.2.10")


@pytest.mark.asyncio
async def test_pause_and_resume():
    renderer = AsyncMock()
    service = DlnaPlaybackService(renderer=renderer)

    track = make_track("track-1", "http://server/1.mp3")

    await service.play(
        "device-1",
        "192.0.2.10",
        "server-1",
        [track],
        "track-1",
    )

    await service.pause("device-1", "192.0.2.10")
    await service.resume("device-1", "192.0.2.10")

    renderer.pause.assert_awaited_once_with("192.0.2.10")
    renderer.resume.assert_awaited_once_with("192.0.2.10")


@pytest.mark.asyncio
async def test_unknown_playback_state():
    service = DlnaPlaybackService(renderer=AsyncMock())

    with pytest.raises(DlnaPlaybackError, match="No active"):
        await service.next("missing-device", "192.0.2.10")


@pytest.mark.asyncio
async def test_stopped_without_playing_does_not_advance():
    renderer = AsyncMock()
    service = DlnaPlaybackService(renderer=renderer)

    first = make_track("track-1", "http://server/1.mp3")
    second = make_track("track-2", "http://server/2.mp3")

    await service.play(
        "device-1",
        "192.0.2.10",
        "server-1",
        [first, second],
        "track-1",
    )
    renderer.reset_mock()

    result = await service.handle_transport_state("device-1", "STOPPED")

    assert result is None
    renderer.play_uri.assert_not_awaited()


@pytest.mark.asyncio
async def test_playing_then_stopped_advances_queue():
    renderer = AsyncMock()
    service = DlnaPlaybackService(renderer=renderer)

    first = make_track("track-1", "http://server/1.mp3")
    second = make_track("track-2", "http://server/2.mp3")

    await service.play(
        "device-1",
        "192.0.2.10",
        "server-1",
        [first, second],
        "track-1",
    )
    renderer.reset_mock()

    await service.handle_transport_state("device-1", "PLAYING")
    result = await service.handle_transport_state("device-1", "STOPPED")

    assert result == second
    renderer.play_uri.assert_awaited_once_with(
        "192.0.2.10",
        "http://server/2.mp3",
    )


@pytest.mark.asyncio
async def test_extra_stopped_after_advance_does_not_advance_again():
    renderer = AsyncMock()
    service = DlnaPlaybackService(renderer=renderer)

    first = make_track("track-1", "http://server/1.mp3")
    second = make_track("track-2", "http://server/2.mp3")
    third = make_track("track-3", "http://server/3.mp3")

    await service.play(
        "device-1",
        "192.0.2.10",
        "server-1",
        [first, second, third],
        "track-1",
    )
    renderer.reset_mock()

    await service.handle_transport_state("device-1", "PLAYING")
    first_result = await service.handle_transport_state("device-1", "STOPPED")
    second_result = await service.handle_transport_state("device-1", "STOPPED")

    assert first_result == second
    assert second_result is None
    renderer.play_uri.assert_awaited_once_with(
        "192.0.2.10",
        "http://server/2.mp3",
    )


@pytest.mark.asyncio
async def test_stopped_at_queue_end_does_not_fail():
    renderer = AsyncMock()
    service = DlnaPlaybackService(renderer=renderer)

    track = make_track("track-1", "http://server/1.mp3")

    await service.play(
        "device-1",
        "192.0.2.10",
        "server-1",
        [track],
        "track-1",
    )
    renderer.reset_mock()

    await service.handle_transport_state("device-1", "PLAYING")
    result = await service.handle_transport_state("device-1", "STOPPED")

    assert result is None
    renderer.play_uri.assert_not_awaited()


@pytest.mark.asyncio
async def test_current_returns_active_item():
    renderer = AsyncMock()
    service = DlnaPlaybackService(renderer=renderer)
    track = make_track("track-1", "http://server/1.mp3")

    await service.play(
        "device-1",
        "192.0.2.10",
        "server-1",
        [track],
        "track-1",
    )

    assert service.current("device-1") == track


@pytest.mark.asyncio
async def test_current_is_empty_after_final_track_stops():
    renderer = AsyncMock()
    service = DlnaPlaybackService(renderer=renderer)
    track = make_track("track-1", "http://server/1.mp3")

    await service.play(
        "device-1",
        "192.0.2.10",
        "server-1",
        [track],
        "track-1",
    )

    await service.handle_transport_state("device-1", "PLAYING")
    await service.handle_transport_state("device-1", "STOPPED")

    assert service.current("device-1") is None
