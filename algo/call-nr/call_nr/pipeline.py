"""DenoiseBackend protocol and the required identity / pass-through backend.

Identity is causal at the contract-A frame: each 480-sample frame is
copied and no future frame is read. ``reset()`` is the hook a stateful
backend uses at call start, call end, and mode switches. The desktop
CLI does file I/O around this API; a future real-time port must not
allocate or touch the filesystem on the audio thread.
"""

from __future__ import annotations

from typing import Protocol

import numpy as np

from call_nr.contract import (
    CONTRACT_A_ID,
    FRAME_SAMPLES_A,
    require_contract_a_rate,
)
from call_nr.io import as_mono_f32


class BackendUnavailable(RuntimeError):
    """Optional backend cannot run because its binary or Python extra is missing."""


class DenoiseBackend(Protocol):
    """Contract-A denoiser.

    ``process`` consumes a whole mono buffer already at the contract
    sample rate and returns audio of the same length. ``process_frame``
    consumes exactly one contract-A frame. ``lookahead_frames`` is 0 when
    the backend does not read future frames, and ``None`` when the
    backend's lookahead is model-defined (DeepFilterNet3) or the desktop
    path is a whole-buffer STFT (GTCRN). Silero VAD is not a
    ``DenoiseBackend``; it writes timestamps from its own CLI.
    """

    name: str
    contract_id: str
    lookahead_frames: int | None

    def reset(self) -> None:
        """Drop streaming state. Identity has none."""

    def process_frame(self, frame: np.ndarray) -> np.ndarray:
        """Return one contract-A frame (480,) from one input frame."""

    def process(self, samples: np.ndarray, sample_rate: int) -> np.ndarray:
        """Return denoised mono float32 of the same length as ``samples``."""


def _frame_view(samples: np.ndarray) -> np.ndarray:
    """Copy ``samples`` into a (n_frames, 480) buffer, zero-padding the tail."""
    mono = as_mono_f32(samples)
    pad = (-mono.size) % FRAME_SAMPLES_A
    if pad:
        mono = np.pad(mono, (0, pad))
    if mono.size == 0:
        return mono.reshape(0, FRAME_SAMPLES_A)
    return mono.reshape(-1, FRAME_SAMPLES_A)


class IdentityBackend:
    """Pass samples through, framed at contract A. No third-party binary."""

    name = "identity"
    contract_id = CONTRACT_A_ID
    lookahead_frames = 0

    def reset(self) -> None:
        return None

    def process_frame(self, frame: np.ndarray) -> np.ndarray:
        block = as_mono_f32(frame)
        if block.shape != (FRAME_SAMPLES_A,):
            raise ValueError(
                f"contract {CONTRACT_A_ID} frame must have shape ({FRAME_SAMPLES_A},), "
                f"got {block.shape}"
            )
        return block.copy()

    def process(self, samples: np.ndarray, sample_rate: int) -> np.ndarray:
        require_contract_a_rate(sample_rate)
        mono = as_mono_f32(samples)
        if mono.size == 0:
            return mono
        framed = _frame_view(mono)
        out = np.empty(framed.shape[0] * FRAME_SAMPLES_A, dtype=np.float32)
        for index, frame in enumerate(framed):
            start = index * FRAME_SAMPLES_A
            out[start : start + FRAME_SAMPLES_A] = self.process_frame(frame)
        return out[: mono.size]


class PassThroughBackend(IdentityBackend):
    """Same processor as identity, registered under the pass-through name."""

    name = "passthrough"
