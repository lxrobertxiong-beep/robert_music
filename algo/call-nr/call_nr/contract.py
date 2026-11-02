"""Public I/O contracts for call-nr.

Two contracts are documented side by side and must not be mixed:

* **A** ``A_48k_480`` — desktop evaluation / comparison boundary.
  48 kHz mono, 10 ms = 480 samples. This is the only contract the
  in-repo processors implement.
* **B** ``B_16k_256`` — on-device pilot frame shape (16 kHz mono,
  256 samples, about 16 ms). Documented so an adapter can be written
  later. This package does not bind a vendor SDK or a firmware
  insertion point, and it does not assume the device graph is 48 kHz.

In-process PCM for contract A is ``float32`` in ``[-1, 1]``. On-disk
WAV written by this package is IEEE float32 (little-endian). The
optional RNNoise backend converts to s16le only at its raw-demo boundary.
"""

from __future__ import annotations

from dataclasses import dataclass

CONTRACT_A_ID = "A_48k_480"
CONTRACT_B_ID = "B_16k_256"

SAMPLE_RATE_A = 48_000
FRAME_SAMPLES_A = 480
FRAME_MS_A = 10

SAMPLE_RATE_B = 16_000
FRAME_SAMPLES_B = 256

PCM_IN_PROCESS = "float32"
PCM_ON_DISK = "float32_wav"


@dataclass(frozen=True)
class Contract:
    """One named frame contract. ``implemented`` is about this package, not a device."""

    id: str
    sample_rate_hz: int
    frame_samples: int
    channels: int = 1
    implemented: bool = False
    notes: str = ""


CONTRACT_A = Contract(
    id=CONTRACT_A_ID,
    sample_rate_hz=SAMPLE_RATE_A,
    frame_samples=FRAME_SAMPLES_A,
    implemented=True,
    notes="Desktop eval/comparison boundary. 10 ms frames.",
)

CONTRACT_B = Contract(
    id=CONTRACT_B_ID,
    sample_rate_hz=SAMPLE_RATE_B,
    frame_samples=FRAME_SAMPLES_B,
    implemented=False,
    notes=(
        "On-device pilot frame shape, documentation only. "
        "SRC between A and B belongs to a future adapter, not this package."
    ),
)


def require_contract_a_rate(sample_rate: int) -> None:
    """Reject any rate other than contract A. Contract B is not silently accepted."""
    if int(sample_rate) != SAMPLE_RATE_A:
        raise ValueError(
            f"processor implements contract {CONTRACT_A_ID} only "
            f"({SAMPLE_RATE_A} Hz mono, {FRAME_SAMPLES_A} samples); got {sample_rate} Hz. "
            f"Resample with call_nr.io first. Contract {CONTRACT_B_ID} "
            f"({SAMPLE_RATE_B} Hz / {FRAME_SAMPLES_B} samples) is documented, not implemented, "
            "and is not a vendor-SDK binding."
        )
