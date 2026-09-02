"""UPnP AVTransport event handling for DLNA playback."""

import asyncio
import logging
from dataclasses import dataclass
from xml.etree import ElementTree

from opencloudtouch.dlna.renderer import DlnaRenderer

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AvTransportEvent:
    """Relevant state from an AVTransport LastChange notification."""

    transport_state: str | None = None
    current_track_uri: str | None = None


def parse_avtransport_event(body: str) -> AvTransportEvent:
    """Parse a UPnP AVTransport NOTIFY body."""
    root = ElementTree.fromstring(body)

    last_change: str | None = None
    for element in root.iter():
        if element.tag.rsplit("}", 1)[-1] == "LastChange":
            last_change = element.text
            break

    if not last_change:
        return AvTransportEvent()

    event_root = ElementTree.fromstring(last_change)

    transport_state: str | None = None
    current_track_uri: str | None = None

    for element in event_root.iter():
        name = element.tag.rsplit("}", 1)[-1]

        if name == "TransportState":
            transport_state = element.attrib.get("val")
        elif name == "CurrentTrackURI":
            current_track_uri = element.attrib.get("val")

    return AvTransportEvent(
        transport_state=transport_state,
        current_track_uri=current_track_uri,
    )


@dataclass
class DlnaSubscription:
    """Active SoundTouch AVTransport subscription."""

    device_id: str
    device_ip: str
    callback_url: str
    sid: str
    timeout_seconds: int
    renewal_task: asyncio.Task[None] | None = None


class DlnaEventSubscriptions:
    """Manage AVTransport subscriptions and their renewal."""

    def __init__(self, renderer: DlnaRenderer):
        self.renderer = renderer
        self._subscriptions: dict[str, DlnaSubscription] = {}

    async def ensure(
        self,
        device_id: str,
        device_ip: str,
        callback_url: str,
    ) -> None:
        """Ensure that a device has an active AVTransport subscription."""
        existing = self._subscriptions.get(device_id)

        if (
            existing is not None
            and existing.device_ip == device_ip
            and existing.callback_url == callback_url
            and existing.renewal_task is not None
            and not existing.renewal_task.done()
        ):
            return

        if existing is not None:
            await self.remove(device_id)

        sid, timeout_seconds = await self.renderer.subscribe(
            device_ip,
            callback_url,
        )

        subscription = DlnaSubscription(
            device_id=device_id,
            device_ip=device_ip,
            callback_url=callback_url,
            sid=sid,
            timeout_seconds=timeout_seconds,
        )
        self._subscriptions[device_id] = subscription
        subscription.renewal_task = asyncio.create_task(self._renew_loop(subscription))

        logger.info(
            "DLNA AVTransport subscribed: device=%s timeout=%ss",
            device_id,
            timeout_seconds,
        )

    async def remove(self, device_id: str) -> None:
        """Remove and unsubscribe an active subscription."""
        subscription = self._subscriptions.pop(device_id, None)
        if subscription is None:
            return

        current_task = asyncio.current_task()
        if (
            subscription.renewal_task is not None
            and subscription.renewal_task is not current_task
        ):
            subscription.renewal_task.cancel()

        try:
            await self.renderer.unsubscribe(
                subscription.device_ip,
                subscription.sid,
            )
        except Exception:
            logger.debug(
                "DLNA AVTransport unsubscribe failed: device=%s",
                device_id,
                exc_info=True,
            )

    async def close(self) -> None:
        """Close all active subscriptions."""
        for device_id in list(self._subscriptions):
            await self.remove(device_id)

    async def _renew_loop(self, subscription: DlnaSubscription) -> None:
        """Renew a subscription before the renderer expires it."""
        try:
            while True:
                delay = max(1, int(subscription.timeout_seconds * 0.8))
                await asyncio.sleep(delay)

                sid, timeout_seconds = await self.renderer.renew_subscription(
                    subscription.device_ip,
                    subscription.sid,
                    subscription.timeout_seconds,
                )

                subscription.sid = sid
                subscription.timeout_seconds = timeout_seconds

                logger.debug(
                    "DLNA AVTransport subscription renewed: device=%s timeout=%ss",
                    subscription.device_id,
                    timeout_seconds,
                )
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.warning(
                "DLNA AVTransport subscription renewal failed: device=%s",
                subscription.device_id,
                exc_info=True,
            )
            self._subscriptions.pop(subscription.device_id, None)
