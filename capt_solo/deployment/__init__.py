"""Governed deployment adapters.

CAPT governs deployment tools without reimplementing them. Adapters expose a
stable lifecycle: plan, preflight, execute, verify, rollback, collect evidence.
"""

from capt_solo.deployment.adapters import (
    DeploymentAdapter,
    DeploymentEvidence,
    DeploymentPlan,
    DeploymentRequest,
    DeploymentResult,
    GovernedDeploymentExecutor,
    LocalScriptDeploymentAdapter,
)

__all__ = [
    "DeploymentAdapter",
    "DeploymentEvidence",
    "DeploymentPlan",
    "DeploymentRequest",
    "DeploymentResult",
    "GovernedDeploymentExecutor",
    "LocalScriptDeploymentAdapter",
]
