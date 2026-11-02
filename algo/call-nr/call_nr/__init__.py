"""Public call-nr skeleton: contract A identity path, optional pinned backends."""

from __future__ import annotations

from call_nr.backends import get_backend
from call_nr.contract import CONTRACT_A_ID, CONTRACT_B_ID
from call_nr.pipeline import (
    BackendUnavailable,
    DenoiseBackend,
    IdentityBackend,
    PassThroughBackend,
)

__version__ = "0.1.0"

__all__ = [
    "CONTRACT_A_ID",
    "CONTRACT_B_ID",
    "BackendUnavailable",
    "DenoiseBackend",
    "IdentityBackend",
    "PassThroughBackend",
    "__version__",
    "get_backend",
]
