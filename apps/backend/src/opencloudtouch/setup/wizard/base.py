"""Shared constructor + constants for the WizardService facade.

Method implementations live in per-step mixin files (step3_connectivity.py,
step4_backup.py, ...) under this package; setup/wizard/service.py composes
them into the single WizardService class used via DI. See
docs/ARCHITECTURE.md "Setup Wizard Subsystem" for the full file map.
"""

from __future__ import annotations


class WizardServiceBase:
    """Constructor and shared constants only — no step logic here."""

    SSH_TIMEOUT: float = 5.0

    def __init__(self, audit_repo=None, device_repo=None) -> None:
        self._audit_repo = audit_repo
        self._device_repo = device_repo
