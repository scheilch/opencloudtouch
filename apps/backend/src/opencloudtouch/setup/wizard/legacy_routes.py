"""Setup Wizard — legacy/superseded endpoints, kept for API-compat only.

CONFIRMED DEAD as of 2026-08-15 (see Task 1 Step 2 of the refactor plan):
no frontend caller for any of the 6 endpoints below. Superseded by
/wizard/scan-backups + /wizard/restore-wizard (config/hosts/backup restore)
and /wizard/finalize (UUID + persistence, folding in what account-pairing/
ensure-account/init-persistence used to do separately).

Do not add new callers here. This file is a deletion candidate — see
docs/superpowers/plans/2026-08-15-refactor-setup-wizard-module.md Task 12.
"""

import logging

from fastapi import APIRouter

from opencloudtouch.core.dependencies import WizardServiceDep
from opencloudtouch.setup.account_pairing_service import ensure_account_uuid
from opencloudtouch.setup.api_models import (
    AccountPairingRequest,
    AccountPairingResponse,
    EnsureAccountRequest,
    EnsureAccountResponse,
    InitPersistenceRequest,
    InitPersistenceResponse,
    ListBackupsRequest,
    ListBackupsResponse,
    RestoreRequest,
    RestoreResponse,
)
from opencloudtouch.setup.config_service import SoundTouchConfigService
from opencloudtouch.setup.hosts_service import SoundTouchHostsService
from opencloudtouch.setup.wizard_helpers import ssh_operation

logger = logging.getLogger(__name__)

legacy_router = APIRouter()


class LegacyWizardMixin:
    """Dead WizardService methods — see wizard_service.py:200,210,220,257 (pre-move)."""

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


@legacy_router.post("/wizard/restore-config", response_model=RestoreResponse)
async def wizard_restore_config(
    request: RestoreRequest,
    wizard: WizardServiceDep,
):
    """Restore config from backup (Wizard Step 8)."""
    logger.info("Restoring config from %s", request.backup_path)

    result = await wizard.restore_config(request.device_ip, request.backup_path)

    if not result["success"]:
        return RestoreResponse(success=False, message=result["message"])
    return RestoreResponse(success=True, message=result["message"])


@legacy_router.post("/wizard/restore-hosts", response_model=RestoreResponse)
async def wizard_restore_hosts(
    request: RestoreRequest,
    wizard: WizardServiceDep,
):
    """Restore hosts from backup (Wizard Step 8)."""
    logger.info("Restoring hosts from %s", request.backup_path)

    result = await wizard.restore_hosts(request.device_ip, request.backup_path)

    if not result["success"]:
        return RestoreResponse(success=False, message=result["message"])
    return RestoreResponse(success=True, message=result["message"])


@legacy_router.post("/wizard/list-backups", response_model=ListBackupsResponse)
async def wizard_list_backups(
    request: ListBackupsRequest,
    wizard: WizardServiceDep,
):
    """List available backups (Wizard Step 8)."""
    logger.info("Listing backups on %s", request.device_ip)

    result = await wizard.list_backups(request.device_ip)

    return ListBackupsResponse(
        success=True,
        config_backups=result["config_backups"],
        hosts_backups=result["hosts_backups"],
    )


@legacy_router.post("/wizard/account-pairing", response_model=AccountPairingResponse)
async def wizard_account_pairing(
    request: AccountPairingRequest,
    wizard: WizardServiceDep,
):
    """Ensure device has a margeAccountUUID (Wizard Step - Account Pairing).

    Checks if the device already has a UUID. If not, generates one and
    sets it via Telnet. Persists the UUID in the device repository for
    streaming endpoint resolution.
    """
    logger.info(
        "Account pairing for %s (device %s)", request.device_ip, request.device_id
    )

    result = await wizard.ensure_account_pairing(request.device_ip, request.device_id)

    return AccountPairingResponse(
        success=result["success"],
        had_uuid=result.get("had_uuid", False),
        uuid=result.get("uuid", ""),
        message=result.get("message", ""),
    )


@legacy_router.post("/wizard/ensure-account", response_model=EnsureAccountResponse)
async def wizard_ensure_account(request: EnsureAccountRequest):
    """Ensure device has a margeAccountUUID (Wizard Step � after config/hosts).

    Devices without a margeAccountUUID cannot play presets (INVALID_SOURCE).
    This endpoint checks GET :8090/info and sets a UUID via Telnet if missing.

    Safe to call multiple times � no-op if UUID already present.
    """
    from opencloudtouch.setup.account_pairing_service import ensure_account_uuid

    logger.info("Ensuring account UUID on device %s", request.device_ip)

    result = await ensure_account_uuid(request.device_ip)

    if not result.success:
        return EnsureAccountResponse(
            success=False,
            had_uuid=result.had_uuid,
            message=result.error or "Account pairing failed",
        )

    return EnsureAccountResponse(
        success=True,
        had_uuid=result.had_uuid,
        uuid=result.uuid,
        message=result.message,
    )


@legacy_router.post("/wizard/init-persistence", response_model=InitPersistenceResponse)
async def wizard_init_persistence(request: InitPersistenceRequest):
    """Initialize persistence files on factory-reset devices (Wizard Step — after account pairing).

    Factory-reset devices lack SystemConfigurationDB.xml and Sources.xml.
    Without them, the firmware never fully initialises playback state,
    causing INVALID_SOURCE on preset recall (GitHub Issue #167).

    Only creates files that are missing — never overwrites existing ones.
    Safe to call multiple times.
    """
    from opencloudtouch.setup.persistence_service import ensure_persistence_files

    logger.info(
        "Initializing persistence files on %s (name=%s, uuid=%s)",
        request.device_ip,
        request.device_name,
        request.account_uuid,
    )

    async with ssh_operation(request.device_ip, "init-persistence") as ssh:
        # Remount rw for file creation
        await ssh.execute("mount -o remount,rw /")
        try:
            result = await ensure_persistence_files(
                ssh=ssh,
                device_name=request.device_name,
                account_uuid=request.account_uuid,
            )
        finally:
            await ssh.execute("sync")
            await ssh.execute("mount -o remount,ro /")

    if not result.success:
        return InitPersistenceResponse(
            success=False,
            message=result.error or "Persistence initialization failed",
        )

    return InitPersistenceResponse(
        success=True,
        created_files=result.created_files,
        skipped_files=result.skipped_files,
        message=result.message,
    )
