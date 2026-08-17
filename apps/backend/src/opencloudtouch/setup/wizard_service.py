"""Wizard orchestration service.

Encapsulates the multi-step wizard business logic. Route handlers delegate
here instead of directly instantiating SSH services and orchestrating steps.
"""

import logging
from datetime import UTC, datetime

from opencloudtouch.setup.account_pairing_service import ensure_account_uuid
from opencloudtouch.setup.config_service import SoundTouchConfigService
from opencloudtouch.setup.hosts_service import SoundTouchHostsService
from opencloudtouch.setup.wizard.step3_connectivity import Step3ConnectivityMixin
from opencloudtouch.setup.wizard.step4_backup import Step4BackupMixin
from opencloudtouch.setup.wizard.step5_config import Step5ConfigMixin
from opencloudtouch.setup.wizard.step6_hosts import Step6HostsMixin
from opencloudtouch.setup.wizard.step7_finalize_verify import Step7FinalizeVerifyMixin
from opencloudtouch.setup.wizard_helpers import ssh_operation

logger = logging.getLogger(__name__)

_ERR_DEVICE_REPO_UNAVAILABLE = "Device repository not available"


class WizardService(
    Step3ConnectivityMixin,
    Step4BackupMixin,
    Step5ConfigMixin,
    Step6HostsMixin,
    Step7FinalizeVerifyMixin,
):
    """Orchestrates the device setup wizard steps.

    Each method corresponds to one wizard step and handles:
    - SSH connection lifecycle
    - Service instantiation
    - Audit trail snapshots
    - Result assembly
    """

    SSH_TIMEOUT: float = 5.0

    def __init__(self, audit_repo=None, device_repo=None) -> None:
        self._audit_repo = audit_repo
        self._device_repo = device_repo

    async def restore_config(self, device_ip: str, backup_path: str) -> dict:
        """Restore config from backup."""
        async with ssh_operation(device_ip, "restore-config") as ssh:
            config_service = SoundTouchConfigService(ssh)
            result = await config_service.restore_config(backup_path)

            if not result.success:
                return {"success": False, "message": result.error or "Restore failed"}
            return {"success": True, "message": "Config restored"}

    async def restore_hosts(self, device_ip: str, backup_path: str) -> dict:
        """Restore hosts from backup."""
        async with ssh_operation(device_ip, "restore-hosts") as ssh:
            hosts_service = SoundTouchHostsService(ssh)
            result = await hosts_service.restore_hosts(backup_path)

            if not result.success:
                return {"success": False, "message": result.error or "Restore failed"}
            return {"success": True, "message": "Hosts restored"}

    async def list_backups(self, device_ip: str) -> dict:
        """List available backups on device."""
        async with ssh_operation(device_ip, "list-backups") as ssh:
            config_service = SoundTouchConfigService(ssh)
            hosts_service = SoundTouchHostsService(ssh)

            config_backups = await config_service.list_backups()
            hosts_backups = await hosts_service.list_backups()

            return {
                "success": True,
                "config_backups": config_backups,
                "hosts_backups": hosts_backups,
            }

    async def ensure_account_pairing(self, device_ip: str, device_id: str) -> dict:
        """Ensure device has a margeAccountUUID — set one via SSH if missing.

        After pairing, persists the UUID to the device repository so the
        streaming endpoint can resolve account_id -> device_id.

        Returns:
            Dict with success, had_uuid, uuid, message
        """
        try:
            result = await ensure_account_uuid(device_ip)

            if result.success and result.uuid and self._device_repo:
                await self._device_repo.update_marge_account_uuid(
                    device_id, result.uuid
                )
                logger.info(
                    "Persisted marge_account_uuid=%s for device %s",
                    result.uuid,
                    device_id,
                )

            return {
                "success": result.success,
                "had_uuid": result.had_uuid,
                "uuid": result.uuid,
                "message": result.message,
                "error": result.error,
            }
        except Exception as e:
            logger.exception("Account pairing failed for %s: %s", device_ip, e)
            return {
                "success": False,
                "had_uuid": False,
                "uuid": "",
                "message": "",
                "error": f"Account pairing failed: {e}",
            }

    async def mark_complete(self, device_id: str) -> dict:
        """Mark wizard setup as complete for a device."""
        if not self._device_repo:
            return {"success": False, "error": _ERR_DEVICE_REPO_UNAVAILABLE}

        try:
            await self._device_repo.update_setup_status(
                device_id=device_id,
                setup_status="configured",
                setup_completed_at=datetime.now(UTC),
            )
            return {"success": True}
        except Exception as e:
            logger.exception("Failed to update setup status for %s", device_id)
            return {"success": False, "error": f"Failed to update setup status: {e}"}
