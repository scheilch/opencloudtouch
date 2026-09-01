"""Tests for SoundTouch UPnP renderer control."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from opencloudtouch.dlna.renderer import DlnaRenderer


@pytest.mark.asyncio
async def test_play_uri():
    renderer = DlnaRenderer()

    response = MagicMock()
    response.raise_for_status = MagicMock()

    client = AsyncMock()
    client.post.return_value = response

    with patch("opencloudtouch.dlna.renderer.httpx.AsyncClient") as client_cls:
        client_cls.return_value.__aenter__.return_value = client

        await renderer.play_uri(
            "192.168.55.26",
            "http://192.168.55.4:8200/MediaItems/24.mp3",
        )

    args, kwargs = client.post.await_args

    assert args[0] == "http://192.168.55.26:8091/AVTransport/Control"
    assert "SetAVTransportURI" in kwargs["content"]
    assert (
        "<CurrentURI>"
        "http://192.168.55.4:8200/MediaItems/24.mp3"
        "</CurrentURI>" in kwargs["content"]
    )
    assert (
        kwargs["headers"]["SOAPAction"]
        == '"urn:schemas-upnp-org:service:AVTransport:1#SetAVTransportURI"'
    )


@pytest.mark.asyncio
async def test_pause():
    renderer = DlnaRenderer()

    with patch.object(renderer, "_send_action", new_callable=AsyncMock) as send:
        await renderer.pause("192.168.55.26")

    send.assert_awaited_once()
    assert send.await_args.args[0] == "192.168.55.26"
    assert send.await_args.args[1] == "Pause"


@pytest.mark.asyncio
async def test_resume():
    renderer = DlnaRenderer()

    with patch.object(renderer, "_send_action", new_callable=AsyncMock) as send:
        await renderer.resume("192.168.55.26")

    send.assert_awaited_once()
    assert send.await_args.args[1] == "Play"


@pytest.mark.asyncio
async def test_renderer_error():
    renderer = DlnaRenderer()

    client = AsyncMock()
    client.post.side_effect = Exception("boom")

    with patch("opencloudtouch.dlna.renderer.httpx.AsyncClient") as client_cls:
        client_cls.return_value.__aenter__.return_value = client

        with pytest.raises(Exception):
            await renderer.play_uri(
                "192.168.55.26",
                "http://example.test/song.mp3",
            )


def test_escape_xml():
    assert DlnaRenderer._escape_xml("a&b<c>") == "a&amp;b&lt;c&gt;"
