"""DLNA application service."""

from opencloudtouch.dlna.client import DlnaClient
from opencloudtouch.dlna.discovery import DlnaDiscovery
from opencloudtouch.dlna.events import DlnaEventSubscriptions
from opencloudtouch.dlna.models import DlnaItem, DlnaServer
from opencloudtouch.dlna.playback import DlnaPlaybackService


class DlnaService:
    """Discover, browse, and play DLNA media."""

    def __init__(
        self,
        discovery: DlnaDiscovery | None = None,
        client: DlnaClient | None = None,
        playback: DlnaPlaybackService | None = None,
    ):
        self.discovery = discovery or DlnaDiscovery()
        self.client = client or DlnaClient()
        self.playback = playback or DlnaPlaybackService()
        self.subscriptions = DlnaEventSubscriptions(self.playback.renderer)

    async def get_servers(self) -> list[DlnaServer]:
        """Discover available DLNA media servers."""
        return await self.discovery.discover()

    async def get_server(self, server_id: str) -> DlnaServer:
        """Resolve a discovered DLNA server by ID."""
        servers = await self.discovery.discover()

        server = next(
            (server for server in servers if server.id == server_id),
            None,
        )

        if server is None:
            raise LookupError(f"DLNA server not found: {server_id}")

        return server

    async def browse(
        self,
        server_id: str,
        object_id: str = "0",
    ) -> list[DlnaItem]:
        """Browse a media server by its discovered server ID."""
        server = await self.get_server(server_id)
        return await self.client.browse(server, object_id)

    async def play(
        self,
        device_id: str,
        device_ip: str,
        server_id: str,
        parent_id: str,
        object_id: str,
        callback_base_url: str,
    ) -> DlnaItem:
        """Play a DLNA item and create a queue from its parent container."""
        items = await self.browse(server_id, parent_id)

        callback_url = f"{callback_base_url.rstrip('/')}/api/dlna/events/{device_id}"
        await self.subscriptions.ensure(
            device_id=device_id,
            device_ip=device_ip,
            callback_url=callback_url,
        )

        return await self.playback.play(
            device_id=device_id,
            device_ip=device_ip,
            server_id=server_id,
            items=items,
            object_id=object_id,
        )

    async def pause(self, device_id: str, device_ip: str) -> None:
        """Pause DLNA playback."""
        await self.playback.pause(device_id, device_ip)

    async def resume(self, device_id: str, device_ip: str) -> None:
        """Resume DLNA playback."""
        await self.playback.resume(device_id, device_ip)

    async def next(self, device_id: str, device_ip: str) -> DlnaItem:
        """Play next DLNA queue item."""
        return await self.playback.next(device_id, device_ip)

    async def previous(self, device_id: str, device_ip: str) -> DlnaItem:
        """Play previous DLNA queue item."""
        return await self.playback.previous(device_id, device_ip)
