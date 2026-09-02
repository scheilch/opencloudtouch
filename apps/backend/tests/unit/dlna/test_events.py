"""Tests for DLNA AVTransport event parsing."""

import asyncio
from unittest.mock import AsyncMock

import pytest

from opencloudtouch.dlna.events import (
    DlnaEventSubscriptions,
    parse_avtransport_event,
)


def test_parse_avtransport_playing_event():
    body = """<?xml version="1.0"?>
<e:propertyset xmlns:e="urn:schemas-upnp-org:event-1-0">
  <e:property>
    <LastChange>&lt;Event xmlns="urn:schemas-upnp-org:metadata-1-0/AVT/"&gt;&lt;InstanceID val="0"&gt;&lt;TransportState val="PLAYING"/&gt;&lt;CurrentTrackURI val="http://media/track.mp3"/&gt;&lt;/InstanceID&gt;&lt;/Event&gt;</LastChange>
  </e:property>
</e:propertyset>"""

    event = parse_avtransport_event(body)

    assert event.transport_state == "PLAYING"
    assert event.current_track_uri == "http://media/track.mp3"


def test_parse_avtransport_stopped_event():
    body = """<?xml version="1.0"?>
<e:propertyset xmlns:e="urn:schemas-upnp-org:event-1-0">
  <e:property>
    <LastChange>&lt;Event xmlns="urn:schemas-upnp-org:metadata-1-0/AVT/"&gt;&lt;InstanceID val="0"&gt;&lt;TransportState val="STOPPED"/&gt;&lt;AVTransportURI val="qplay://"/&gt;&lt;/InstanceID&gt;&lt;/Event&gt;</LastChange>
  </e:property>
</e:propertyset>"""

    event = parse_avtransport_event(body)

    assert event.transport_state == "STOPPED"
    assert event.current_track_uri is None


@pytest.mark.asyncio
async def test_subscription_is_created():
    renderer = AsyncMock()
    renderer.subscribe.return_value = ("uuid:test-subscription", 300)

    subscriptions = DlnaEventSubscriptions(renderer)

    await subscriptions.ensure(
        device_id="device-1",
        device_ip="192.0.2.10",
        callback_url="http://192.0.2.20:7777/api/dlna/events/device-1",
    )

    renderer.subscribe.assert_awaited_once_with(
        "192.0.2.10",
        "http://192.0.2.20:7777/api/dlna/events/device-1",
    )

    subscription = subscriptions._subscriptions["device-1"]
    assert subscription.sid == "uuid:test-subscription"
    assert subscription.timeout_seconds == 300

    await subscriptions.remove("device-1")


@pytest.mark.asyncio
async def test_existing_subscription_is_reused():
    renderer = AsyncMock()
    renderer.subscribe.return_value = ("uuid:test-subscription", 300)

    subscriptions = DlnaEventSubscriptions(renderer)

    await subscriptions.ensure(
        "device-1",
        "192.0.2.10",
        "http://192.0.2.20:7777/api/dlna/events/device-1",
    )
    await subscriptions.ensure(
        "device-1",
        "192.0.2.10",
        "http://192.0.2.20:7777/api/dlna/events/device-1",
    )

    renderer.subscribe.assert_awaited_once()

    await subscriptions.remove("device-1")


@pytest.mark.asyncio
async def test_remove_unsubscribes():
    renderer = AsyncMock()
    renderer.subscribe.return_value = ("uuid:test-subscription", 300)

    subscriptions = DlnaEventSubscriptions(renderer)

    await subscriptions.ensure(
        "device-1",
        "192.0.2.10",
        "http://192.0.2.20:7777/api/dlna/events/device-1",
    )
    await subscriptions.remove("device-1")

    renderer.unsubscribe.assert_awaited_once_with(
        "192.0.2.10",
        "uuid:test-subscription",
    )
    assert "device-1" not in subscriptions._subscriptions


@pytest.mark.asyncio
async def test_subscription_is_renewed(monkeypatch):
    renderer = AsyncMock()
    renderer.subscribe.return_value = ("uuid:original", 300)
    renderer.renew_subscription.return_value = ("uuid:renewed", 300)

    subscriptions = DlnaEventSubscriptions(renderer)

    sleep_calls = 0

    async def fake_sleep(delay):
        nonlocal sleep_calls
        sleep_calls += 1

        assert delay == 240

        if sleep_calls > 1:
            raise asyncio.CancelledError

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)

    await subscriptions.ensure(
        "device-1",
        "192.0.2.10",
        "http://192.0.2.20:7777/api/dlna/events/device-1",
    )

    task = subscriptions._subscriptions["device-1"].renewal_task

    with pytest.raises(asyncio.CancelledError):
        await task

    renderer.renew_subscription.assert_awaited_once_with(
        "192.0.2.10",
        "uuid:original",
        300,
    )

    assert subscriptions._subscriptions["device-1"].sid == "uuid:renewed"
