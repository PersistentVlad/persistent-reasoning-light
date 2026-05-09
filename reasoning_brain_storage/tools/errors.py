# Copyright (c) 2026 Vladislav Bliznyukov
# Licensed under the Apache License 2.0
# This file is part of persistent-reasoning-light

class BrainStorageError(Exception):
    """
    Base error for reasoning brain storage tools.
    """


class BrainValidationError(BrainStorageError):
    """
    Raised when storage inputs or brain structure are invalid.

    Examples:
    - invalid runtime root
    - malformed persisted artifact structure
    - unsupported value types for persistence
    """


class BrainMutationError(BrainStorageError):
    """
    Raised when a forbidden or unsafe mutation is attempted.

    Examples:
    - mutation of immutable brain state
    - forbidden in-place rewrite
    - mutation through a read-only operation
    """


class BrainConflictError(BrainStorageError):
    """
    Raised when a storage operation would silently overwrite or conflict with
    existing reasoning state.

    Important:
    This is a storage-layer conflict, not a governance rejection.

    Examples:
    - persisting an artifact to an already existing path
    - creating a snapshot where the target already exists
    - initializing brain into a non-empty target location
    """