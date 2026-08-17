"""Wizard orchestration service.

Encapsulates the multi-step wizard business logic. Route handlers delegate
here instead of directly instantiating SSH services and orchestrating steps.
"""

from opencloudtouch.setup.wizard.legacy_routes import LegacyWizardMixin
from opencloudtouch.setup.wizard.step3_connectivity import Step3ConnectivityMixin
from opencloudtouch.setup.wizard.step4_backup import Step4BackupMixin
from opencloudtouch.setup.wizard.step5_config import Step5ConfigMixin
from opencloudtouch.setup.wizard.step6_hosts import Step6HostsMixin
from opencloudtouch.setup.wizard.step7_finalize_verify import Step7FinalizeVerifyMixin
from opencloudtouch.setup.wizard.step8_completion import Step8CompletionMixin


class WizardService(
    Step3ConnectivityMixin,
    Step4BackupMixin,
    Step5ConfigMixin,
    Step6HostsMixin,
    Step7FinalizeVerifyMixin,
    Step8CompletionMixin,
    LegacyWizardMixin,
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
