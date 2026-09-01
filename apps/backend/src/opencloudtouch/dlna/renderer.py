"""UPnP AVTransport client for SoundTouch playback."""

import httpx


class DlnaRendererError(Exception):
    """Raised when communication with a UPnP renderer fails."""


class DlnaRenderer:
    """Control SoundTouch playback through its UPnP AVTransport service."""

    AVTRANSPORT_SERVICE = "urn:schemas-upnp-org:service:AVTransport:1"

    def __init__(self, timeout: float = 5.0):
        self.timeout = timeout

    async def play_uri(self, device_ip: str, uri: str) -> None:
        """Set a media URI on a SoundTouch device.

        SoundTouch devices start playback automatically after
        SetAVTransportURI, so no separate Play action is required.
        """
        await self._send_action(
            device_ip,
            "SetAVTransportURI",
            f"""
      <InstanceID>0</InstanceID>
      <CurrentURI>{self._escape_xml(uri)}</CurrentURI>
      <CurrentURIMetaData></CurrentURIMetaData>
""",
        )

    async def pause(self, device_ip: str) -> None:
        """Pause current playback."""
        await self._send_action(
            device_ip,
            "Pause",
            """
      <InstanceID>0</InstanceID>
""",
        )

    async def resume(self, device_ip: str) -> None:
        """Resume current playback."""
        await self._send_action(
            device_ip,
            "Play",
            """
      <InstanceID>0</InstanceID>
      <Speed>1</Speed>
""",
        )

    async def _send_action(
        self,
        device_ip: str,
        action: str,
        body: str,
    ) -> None:
        """Send an AVTransport SOAP action."""
        url = f"http://{device_ip}:8091/AVTransport/Control"

        payload = f"""<?xml version="1.0" encoding="utf-8"?>
<s:Envelope
    xmlns:s="http://schemas.xmlsoap.org/soap/envelope/"
    s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">
  <s:Body>
    <u:{action} xmlns:u="{self.AVTRANSPORT_SERVICE}">
{body.rstrip()}
    </u:{action}>
  </s:Body>
</s:Envelope>"""

        headers = {
            "Content-Type": 'text/xml; charset="utf-8"',
            "SOAPAction": f'"{self.AVTRANSPORT_SERVICE}#{action}"',
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    url,
                    content=payload,
                    headers=headers,
                )
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise DlnaRendererError(
                f"SoundTouch renderer request failed: {action}"
            ) from exc

    @staticmethod
    def _escape_xml(value: str) -> str:
        """Escape text inserted into SOAP XML."""
        return (
            value.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&apos;")
        )
