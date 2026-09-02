"""Tests for the DLNA application service."""

from unittest.mock import AsyncMock

import pytest

from opencloudtouch.dlna.models import DlnaItem, DlnaServer
from opencloudtouch.dlna.service import DlnaService


@pytest.mark.asyncio
async def test_get_servers():
    server = DlnaServer(
        id="server-1",
        name="Test Server",
        location="http://192.0.2.10/device.xml",
        control_url="http://192.0.2.10/content/control",
    )

    discovery = AsyncMock()
    discovery.discover.return_value = [server]

    service = DlnaService(discovery=discovery)

    result = await service.get_servers()

    assert result == [server]


@pytest.mark.asyncio
async def test_browse_server():
    server = DlnaServer(
        id="server-1",
        name="Test Server",
        location="http://192.0.2.10/device.xml",
        control_url="http://192.0.2.10/content/control",
    )
    item = DlnaItem(
        id="track-1",
        parent_id="0",
        title="Track",
        is_container=False,
    )

    discovery = AsyncMock()
    discovery.discover.return_value = [server]

    client = AsyncMock()
    client.browse.return_value = [item]

    service = DlnaService(
        discovery=discovery,
        client=client,
    )

    result = await service.browse("server-1", "0")

    assert result == [item]
    client.browse.assert_awaited_once_with(server, "0")


@pytest.mark.asyncio
async def test_browse_unknown_server():
    discovery = AsyncMock()
    discovery.discover.return_value = []

    service = DlnaService(discovery=discovery)

    with pytest.raises(LookupError):
        await service.browse("missing-server")


@pytest.mark.asyncio
async def test_play_dlna_item():
    service = DlnaService()

    server = DlnaServer(
        id="server-1",
        name="Test Server",
        location="http://server/root.xml",
        control_url="http://server/content",
    )
    item = DlnaItem(
        id="track-1",
        parent_id="folder-1",
        title="Track",
        is_container=False,
        resource_url="http://server/track.mp3",
        media_class="object.item.audioItem.musicTrack",
    )

    service.discovery.discover = AsyncMock(return_value=[server])
    service.client.browse = AsyncMock(return_value=[item])
    service.subscriptions.ensure = AsyncMock()
    service.playback.play = AsyncMock(return_value=item)

    result = await service.play(
        device_id="device-1",
        device_ip="192.168.1.10",
        server_id="server-1",
        parent_id="folder-1",
        object_id="track-1",
        callback_base_url="http://oct.local:7777",
    )

    assert result == item

    service.subscriptions.ensure.assert_awaited_once_with(
        device_id="device-1",
        device_ip="192.168.1.10",
        callback_url="http://oct.local:7777/api/dlna/events/device-1",
    )
    service.playback.play.assert_awaited_once_with(
        device_id="device-1",
        device_ip="192.168.1.10",
        server_id="server-1",
        items=[item],
        object_id="track-1",
    )


@pytest.mark.asyncio
async def test_playback_controls():
    service = DlnaService()

    service.playback.pause = AsyncMock()
    service.playback.resume = AsyncMock()
    service.playback.next = AsyncMock()
    service.playback.previous = AsyncMock()

    await service.pause("device-1", "192.168.1.10")
    await service.resume("device-1", "192.168.1.10")
    await service.next("device-1", "192.168.1.10")
    await service.previous("device-1", "192.168.1.10")

    service.playback.pause.assert_awaited_once_with("device-1", "192.168.1.10")
    service.playback.resume.assert_awaited_once_with("device-1", "192.168.1.10")
    service.playback.next.assert_awaited_once_with("device-1", "192.168.1.10")
    service.playback.previous.assert_awaited_once_with("device-1", "192.168.1.10")
