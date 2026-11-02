"""Checks for optional local checkouts and weight files.

This module never clones a repository and never downloads a checkpoint.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from call_nr.pipeline import BackendUnavailable

LFS_MARKER = b"version https://git-lfs.github.com/spec/v1"
MIN_WEIGHT_BYTES = 10_000


def assert_real_weight(path: Path, *, label: str) -> Path:
    """Return ``path`` when it is a real weight file, else raise a clear error."""
    if not path.is_file():
        raise BackendUnavailable(
            f"{label} is not a file: {path}. This package does not download weights."
        )
    size = path.stat().st_size
    with path.open("rb") as handle:
        head = handle.read(len(LFS_MARKER) + 8)
    if head.startswith(LFS_MARKER) or size < MIN_WEIGHT_BYTES:
        raise BackendUnavailable(
            f"{label} at {path} is not a usable weight file ({size} bytes). "
            "Git LFS pointers and truncated downloads are rejected. "
            "Fetch the real file from the pinned upstream checkout. "
            "This package does not download weights."
        )
    return path


def assert_pinned_commit(root: Path, expected: str, *, label: str) -> None:
    """If ``root`` is a git checkout, require ``HEAD`` to be ``expected``.

    A copied tree with no ``.git`` directory is accepted: the caller already
    had to point at it explicitly, and the docs state which commit to copy.
    """
    if not (root / ".git").exists():
        return
    try:
        head = subprocess.check_output(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise BackendUnavailable(
            f"{label} at {root} has a .git directory but HEAD could not be read ({exc}). "
            f"Expected commit {expected}."
        ) from exc
    if head != expected:
        raise BackendUnavailable(
            f"{label} at {root} is at {head}, not the pinned commit {expected}. "
            "Check out that commit. This package does not vendor the upstream tree."
        )
