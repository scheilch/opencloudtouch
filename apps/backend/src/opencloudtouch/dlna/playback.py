"""DLNA playback and in-memory queue management."""

from dataclasses import dataclass

from opencloudtouch.dlna.models import DlnaItem
from opencloudtouch.dlna.renderer import DlnaRenderer


class DlnaPlaybackError(Exception):
    """Raised when a DLNA playback operation cannot be completed."""


@dataclass
class DlnaPlaybackState:
    """Current DLNA playback state for one device."""

    server_id: str
    items: list[DlnaItem]
    index: int
    device_ip: str
    playing_seen: bool = False

    @property
    def current_item(self) -> DlnaItem:
        """Return the currently selected item."""
        return self.items[self.index]


class DlnaPlaybackService:
    """Manage DLNA playback and navigation per SoundTouch device."""

    def __init__(self, renderer: DlnaRenderer | None = None):
        self.renderer = renderer or DlnaRenderer()
        self._states: dict[str, DlnaPlaybackState] = {}

    async def play(
        self,
        device_id: str,
        device_ip: str,
        server_id: str,
        items: list[DlnaItem],
        object_id: str,
    ) -> DlnaItem:
        """Play an item and remember its surrounding audio queue."""
        playable_items = [
            item
            for item in items
            if not item.is_container
            and item.resource_url
            and (
                item.media_class is None
                or item.media_class.startswith("object.item.audioItem")
            )
        ]

        index = next(
            (
                index
                for index, item in enumerate(playable_items)
                if item.id == object_id
            ),
            None,
        )

        if index is None:
            raise DlnaPlaybackError(f"DLNA audio item not found: {object_id}")

        state = DlnaPlaybackState(
            server_id=server_id,
            items=playable_items,
            index=index,
            device_ip=device_ip,
        )

        self._states[device_id] = state

        await self._play_item(device_ip, state.current_item)
        return state.current_item

    async def pause(self, device_id: str, device_ip: str) -> None:
        """Pause the current item."""
        self._require_state(device_id)
        await self.renderer.pause(device_ip)

    async def resume(self, device_id: str, device_ip: str) -> None:
        """Resume the current item."""
        self._require_state(device_id)
        await self.renderer.resume(device_ip)

    async def next(self, device_id: str, device_ip: str) -> DlnaItem:
        """Play the next item in the current queue."""
        state = self._require_state(device_id)

        if state.index >= len(state.items) - 1:
            raise DlnaPlaybackError("No next DLNA track")

        state.index += 1
        state.playing_seen = False
        await self._play_item(device_ip, state.current_item)
        return state.current_item

    async def previous(self, device_id: str, device_ip: str) -> DlnaItem:
        """Play the previous item in the current queue."""
        state = self._require_state(device_id)

        if state.index <= 0:
            raise DlnaPlaybackError("No previous DLNA track")

        state.index -= 1
        state.playing_seen = False
        await self._play_item(device_ip, state.current_item)
        return state.current_item

    async def handle_transport_state(
        self,
        device_id: str,
        transport_state: str,
    ) -> DlnaItem | None:
        """Advance the queue after a played track reaches STOPPED."""
        state = self._states.get(device_id)
        if state is None:
            return None

        if transport_state == "PLAYING":
            state.playing_seen = True
            return None

        if transport_state != "STOPPED" or not state.playing_seen:
            return None

        # Disarm before changing URI. SetAVTransportURI itself produces
        # STOPPED/TRANSITIONING events which must not advance again.
        state.playing_seen = False

        if state.index >= len(state.items) - 1:
            return None

        state.index += 1
        await self._play_item(state.device_ip, state.current_item)
        return state.current_item

    async def _play_item(self, device_ip: str, item: DlnaItem) -> None:
        """Send a playable item to the SoundTouch renderer."""
        if not item.resource_url:
            raise DlnaPlaybackError(f"DLNA item has no playable resource: {item.id}")

        await self.renderer.play_uri(device_ip, item.resource_url)

    def _require_state(self, device_id: str) -> DlnaPlaybackState:
        """Return playback state or raise when none exists."""
        state = self._states.get(device_id)

        if state is None:
            raise DlnaPlaybackError(f"No active DLNA playback for device: {device_id}")

        return state
