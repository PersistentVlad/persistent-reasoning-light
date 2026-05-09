# Copyright (c) 2026 Vladislav Bliznyukov
# Licensed under the Apache License 2.0
# This file is part of persistent-reasoning-light

class GovernanceLightError(Exception):
    """
    Base error for reasoning_governance_light.
    """


class GovernanceContractViolation(GovernanceLightError):
    """
    Raised when the caller violates the governance-light contract.

    Examples:
    - candidate is not a mapping
    - brain_state is not a read-only structured snapshot
    - artifact contains unsupported value types
    """