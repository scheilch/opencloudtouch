"""
Setup Wizard API Routes � Thin Handlers

SSH-driven step-by-step wizard endpoints for device configuration.
All business logic lives in WizardService; routes only handle HTTP concerns.
"""

import logging
from typing import Annotated, Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from fastapi import status as http_status

from opencloudtouch.core.dependencies import RestoreServiceDep, get_wizard_service
from opencloudtouch.setup.api_models import (
    AccountPairingRequest,
    AccountPairingResponse,
    ConnectivityCheckRequest,
    EnsureAccountRequest,
    EnsureAccountResponse,
    FinalizeRequest,
    FinalizeResponse,
    HostsModifyRequest,
    HostsModifyResponse,
    InitPersistenceRequest,
    InitPersistenceResponse,
    ListBackupsRequest,
    ListBackupsResponse,
    RestoreRequest,
    RestoreResponse,
    RestoreStepResponse,
    RestoreWizardRequest,
    RestoreWizardResponse,
    ScanBackupsRequest,
    ScanBackupsResponse,
    VerifyRedirectRequest,
    VerifyRedirectResponse,
    VerifySetupRequest,
    VerifySetupResponse,
    WizardCompleteRequest,
    WizardCompleteResponse,
)
from opencloudtouch.setup.wizard.step3_connectivity import step3_router
from opencloudtouch.setup.wizard.step4_backup import step4_router
from opencloudtouch.setup.wizard.step5_config import step5_router
from opencloudtouch.setup.wizard.strategy import strategy_router
from opencloudtouch.setup.wizard_helpers import ssh_operation
from opencloudtouch.setup.wizard_service import WizardService

logger = logging.getLogger(__name__)

wizard_router = APIRouter(prefix="/api/setup", tags=["Setup Wizard"])
wizard_router.include_router(strategy_router)
wizard_router.include_router(step3_router)
wizard_router.include_router(step4_router)
wizard_router.include_router(step5_router)


@wizard_router.post("/wizard/modify-hosts", response_model=HostsModifyResponse)
async def wizard_modify_hosts(
    request: HostsModifyRequest,
    wizard: Annotated[WizardService, Depends(get_wizard_service)],
):
    """Modify /etc/hosts (Wizard Step 6)."""
    logger.info(
        "Modifying hosts on %s (OCT: %s)", request.device_ip, request.target_addr
    )

    try:
        result = await wizard.modify_hosts(
            request.device_ip, request.target_addr, request.include_optional
        )
    except ValueError as e:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    if not result["success"]:
        return HostsModifyResponse(success=False, message=result["message"])

    return HostsModifyResponse(
        success=True,
        message=result["message"],
        backup_path=result.get("backup_path", ""),
        diff=result.get("diff", ""),
    )


@wizard_router.post("/wizard/restore-config", response_model=RestoreResponse)
async def wizard_restore_config(
    request: RestoreRequest,
    wizard: Annotated[WizardService, Depends(get_wizard_service)],
):
    """Restore config from backup (Wizard Step 8)."""
    logger.info("Restoring config from %s", request.backup_path)

    result = await wizard.restore_config(request.device_ip, request.backup_path)

    if not result["success"]:
        return RestoreResponse(success=False, message=result["message"])
    return RestoreResponse(success=True, message=result["message"])


@wizard_router.post("/wizard/restore-hosts", response_model=RestoreResponse)
async def wizard_restore_hosts(
    request: RestoreRequest,
    wizard: Annotated[WizardService, Depends(get_wizard_service)],
):
    """Restore hosts from backup (Wizard Step 8)."""
    logger.info("Restoring hosts from %s", request.backup_path)

    result = await wizard.restore_hosts(request.device_ip, request.backup_path)

    if not result["success"]:
        return RestoreResponse(success=False, message=result["message"])
    return RestoreResponse(success=True, message=result["message"])


@wizard_router.post("/wizard/list-backups", response_model=ListBackupsResponse)
async def wizard_list_backups(
    request: ListBackupsRequest,
    wizard: Annotated[WizardService, Depends(get_wizard_service)],
):
    """List available backups (Wizard Step 8)."""
    logger.info("Listing backups on %s", request.device_ip)

    result = await wizard.list_backups(request.device_ip)

    return ListBackupsResponse(
        success=True,
        config_backups=result["config_backups"],
        hosts_backups=result["hosts_backups"],
    )


@wizard_router.post("/wizard/reboot-device")
async def wizard_reboot_device(
    request: ConnectivityCheckRequest,
    wizard: Annotated[WizardService, Depends(get_wizard_service)],
) -> Dict[str, Any]:
    """Reboot SoundTouch device via SSH (Wizard Step 7)."""
    logger.info("Sending reboot command to %s", request.ip)

    result = await wizard.reboot_device(request.ip)

    if not result["success"]:
        error_msg = result["error"]
        # Connection failures ? 503; unexpected errors ? 500
        if "SSH connection failed" in error_msg:
            status_code = http_status.HTTP_503_SERVICE_UNAVAILABLE
        else:
            status_code = http_status.HTTP_500_INTERNAL_SERVER_ERROR
        raise HTTPException(status_code=status_code, detail=error_msg)

    logger.info("Reboot command sent to %s", request.ip)
    return {
        "success": True,
        "message": "Neustart-Befehl gesendet. Das Ger�t startet in wenigen Sekunden neu.",
    }


@wizard_router.post("/wizard/account-pairing", response_model=AccountPairingResponse)
async def wizard_account_pairing(
    request: AccountPairingRequest,
    wizard: Annotated[WizardService, Depends(get_wizard_service)],
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


@wizard_router.post("/wizard/ensure-account", response_model=EnsureAccountResponse)
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


@wizard_router.post("/wizard/init-persistence", response_model=InitPersistenceResponse)
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


@wizard_router.post("/wizard/complete", response_model=WizardCompleteResponse)
async def wizard_complete(
    request: WizardCompleteRequest,
    wizard: Annotated[WizardService, Depends(get_wizard_service)],
):
    """Mark wizard setup as complete for a device."""
    logger.info("Marking wizard setup complete for device %s", request.device_id)

    result = await wizard.mark_complete(request.device_id)

    if not result["success"]:
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=result["error"],
        )

    return WizardCompleteResponse(
        success=True,
        device_id=request.device_id,
        setup_status="configured",
        message="Setup abgeschlossen. Ger�t ist konfiguriert.",
    )


@wizard_router.post("/wizard/verify-redirect", response_model=VerifyRedirectResponse)
async def wizard_verify_redirect(
    request: VerifyRedirectRequest,
    wizard: Annotated[WizardService, Depends(get_wizard_service)],
):
    """Verify a domain is redirected to OCT on the device (Wizard Step 7)."""
    logger.info(
        "Verifying redirect of %s on %s (expected: %s)",
        request.domain,
        request.device_ip,
        request.expected_ip,
    )

    result = await wizard.verify_redirect(
        request.device_ip, request.domain, request.expected_ip
    )

    return VerifyRedirectResponse(
        success=result["matches_expected"],
        domain=result["domain"],
        resolved_ip=result["resolved_ip"],
        expected_ip=result["expected_ip"],
        matches_expected=result["matches_expected"],
        message=result["message"],
    )


@wizard_router.post(
    "/wizard/finalize",
    response_model=FinalizeResponse,
    responses={500: {"description": "Finalization failed"}},
)
async def wizard_finalize(
    request: FinalizeRequest,
    wizard: Annotated[WizardService, Depends(get_wizard_service)],
):
    """Finalize device setup: set UUID + write Sources.xml (Issue #184).

    Atomic operation that ensures the device has a unique margeAccountUUID
    and a complete Sources.xml. Safe to call multiple times (idempotent).
    """
    logger.info("Finalizing device %s (%s)", request.device_id, request.device_ip)

    result = await wizard.finalize_device(request.device_ip, request.device_id)

    if not result["success"]:
        return FinalizeResponse(
            success=False,
            error=result.get("error", "Finalization failed"),
        )

    return FinalizeResponse(
        success=True,
        uuid=result.get("uuid", ""),
        had_uuid=result.get("had_uuid", False),
        uuid_was_collision=result.get("uuid_was_collision", False),
        sources_written=result.get("sources_written", False),
        sources_backup_path=result.get("sources_backup_path", ""),
        system_config_written=result.get("system_config_written", False),
        message=result.get("message", ""),
    )


@wizard_router.post(
    "/wizard/verify-setup",
    response_model=VerifySetupResponse,
    responses={500: {"description": "Verification failed"}},
)
async def wizard_verify_setup(
    request: VerifySetupRequest,
    wizard: Annotated[WizardService, Depends(get_wizard_service)],
):
    """Comprehensive post-setup health check (Issue #184).

    Read-only validation: checks UUID, Sources.xml, config files,
    hosts entries, and SystemConfigurationDB.xml. Never modifies device.
    """
    logger.info(
        "Verifying setup for %s (%s, expected OCT IP: %s)",
        request.device_id,
        request.device_ip,
        request.expected_oct_ip,
    )

    result = await wizard.verify_setup(
        request.device_ip, request.device_id, request.expected_oct_ip
    )

    return VerifySetupResponse(
        success=result["success"],
        checks=result.get("checks", []),
        passed_count=result.get("passed_count", 0),
        failed_count=result.get("failed_count", 0),
        message=result.get("message", ""),
    )


# ============================================================================
# Restore Wizard Endpoints
# ============================================================================


@wizard_router.post(
    "/wizard/scan-backups",
    response_model=ScanBackupsResponse,
    responses={500: {"description": "Backup scan failed"}},
)
async def wizard_scan_backups(
    request: ScanBackupsRequest,
    restore: RestoreServiceDep,
):
    """Scan USB stick for backup files and auto-select matching set."""
    logger.info(
        "Scanning backups on %s for device %s", request.device_ip, request.device_id
    )
    try:
        result = await restore.scan_backups(request.device_ip, request.device_id)
        return ScanBackupsResponse(
            usb_mounted=result.usb_mounted,
            backup_dir=result.backup_dir,
            selected_set=_backup_set_to_response(result.selected_set),
            all_sets=[_backup_set_to_response(s) for s in result.all_sets],
            error=result.error,
        )
    except Exception as e:
        logger.exception("Backup scan failed")
        raise HTTPException(status_code=500, detail=str(e))


@wizard_router.post(
    "/wizard/restore-wizard",
    response_model=RestoreWizardResponse,
    responses={500: {"description": "Restore wizard execution failed"}},
)
async def wizard_restore_wizard(
    request: RestoreWizardRequest,
    restore: RestoreServiceDep,
):
    """Execute full restore wizard sequence."""
    logger.info(
        "Executing %s restore on %s (device %s)",
        request.restore_type,
        request.device_ip,
        request.device_id,
    )
    try:
        backup_set_dict = None
        if request.backup_set:
            backup_set_dict = {
                "device_id": request.backup_set.device_id,
                "backup_date": request.backup_set.backup_date,
                "files": [
                    {"file_path": f.file_path, "volume_type": f.volume_type}
                    for f in request.backup_set.files
                ],
            }
        result = await restore.execute_restore(
            device_ip=request.device_ip,
            device_id=request.device_id,
            restore_type=request.restore_type,
            backup_set=backup_set_dict,
            skip_snapshot=request.skip_snapshot,
        )
        return RestoreWizardResponse(
            success=result.success,
            restore_type=result.restore_type,
            steps=[
                RestoreStepResponse(
                    name=s.name.value if hasattr(s.name, "value") else s.name,
                    status=s.status.value if hasattr(s.status, "value") else s.status,
                    message=s.message,
                    error=s.error,
                    duration_seconds=s.duration_seconds,
                )
                for s in result.steps
            ],
            pre_restore_snapshot=result.pre_restore_snapshot,
            snapshot_skipped=result.snapshot_skipped,
            device_rebooted=result.device_rebooted,
            total_duration_seconds=result.total_duration_seconds,
        )
    except Exception as e:
        logger.exception("Restore wizard failed")
        raise HTTPException(status_code=500, detail=str(e))


def _backup_set_to_response(bs):
    """Convert domain BackupSet to API response model."""
    if bs is None:
        return None
    from opencloudtouch.setup.api_models import (
        BackupFileInfoResponse,
        BackupSetResponse,
    )

    return BackupSetResponse(
        device_id=bs.device_id,
        backup_date=bs.backup_date,
        files=[
            BackupFileInfoResponse(
                filename=f.filename,
                volume_type=f.volume_type,
                file_path=f.file_path,
                size_bytes=f.size_bytes,
                device_id=f.device_id,
                backup_date=f.backup_date,
                is_pre_restore=f.is_pre_restore,
                validation_status=(
                    f.validation_status.value
                    if hasattr(f.validation_status, "value")
                    else f.validation_status
                ),
                validation_message=f.validation_message,
            )
            for f in bs.files
        ],
        is_legacy=bs.is_legacy,
        is_match=bs.is_match,
    )
