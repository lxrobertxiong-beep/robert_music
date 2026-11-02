"""Optional RNNoise@v0.2 adapter.

Talks to an external ``examples/rnnoise_demo`` binary. This package does
not vendor RNNoise. Set ``RNNOISE_DEMO`` to the executable or
``RNNOISE_ROOT`` to a local checkout of commit
``904a876dce1f9ab8860c0a5000ed151f9f6eef58`` (tag ``v0.2``). A checkout
placed at ``algo/call-nr/third_party/rnnoise`` is also accepted and is
gitignored.

The demo consumes raw s16le mono at 48 kHz in 480-sample frames. Build
upstream with ``./autogen.sh && ./configure && make`` (autoconf,
automake, libtool, pkg-config).
"""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path

import numpy as np

from call_nr.contract import (
    CONTRACT_A_ID,
    FRAME_SAMPLES_A,
    SAMPLE_RATE_A,
    require_contract_a_rate,
)
from call_nr.io import as_mono_f32
from call_nr.pipeline import BackendUnavailable

RNNOISE_TAG = "v0.2"
RNNOISE_COMMIT = "904a876dce1f9ab8860c0a5000ed151f9f6eef58"


def _candidate_roots() -> list[Path]:
    roots: list[Path] = []
    env_root = os.environ.get("RNNOISE_ROOT")
    if env_root:
        roots.append(Path(env_root))
    plugin_root = Path(__file__).resolve().parents[2]
    roots.append(plugin_root / "third_party" / "rnnoise")
    return roots


def resolve_rnnoise_demo() -> Path:
    """Find ``rnnoise_demo`` or raise ``BackendUnavailable`` with build hints."""
    env_demo = os.environ.get("RNNOISE_DEMO")
    if env_demo:
        demo = Path(env_demo)
        if demo.is_file() and os.access(demo, os.X_OK):
            return demo
        raise BackendUnavailable(
            f"RNNOISE_DEMO is not an executable file: {demo}. "
            f"Build RNNoise@{RNNOISE_TAG} ({RNNOISE_COMMIT}) so examples/rnnoise_demo exists."
        )

    for root in _candidate_roots():
        cand = root / "examples" / "rnnoise_demo"
        if cand.is_file() and os.access(cand, os.X_OK):
            return cand

    raise BackendUnavailable(
        "RNNoise demo not found. This package does not vendor the binary. "
        f"Clone RNNoise@{RNNOISE_TAG} at {RNNOISE_COMMIT}, build with "
        "./autogen.sh && ./configure && make (needs autoconf automake libtool pkg-config), "
        "then set RNNOISE_DEMO to examples/rnnoise_demo or RNNOISE_ROOT to the checkout. "
        "CI does not download this pin."
    )


def _float_to_s16(samples: np.ndarray) -> np.ndarray:
    scaled = np.clip(np.rint(samples.astype(np.float64) * 32767.0), -32768, 32767)
    return scaled.astype(np.int16)


def _s16_to_float(pcm: np.ndarray) -> np.ndarray:
    return np.ascontiguousarray(pcm.astype(np.float32) / 32768.0)


class RNNoiseBackend:
    """File-oriented RNNoise@v0.2 at contract A. Unavailable without the demo binary."""

    name = "rnnoise"
    contract_id = CONTRACT_A_ID
    lookahead_frames = 0

    def reset(self) -> None:
        return None

    def process_frame(self, frame: np.ndarray) -> np.ndarray:
        return self.process(frame, SAMPLE_RATE_A)

    def process(self, samples: np.ndarray, sample_rate: int) -> np.ndarray:
        require_contract_a_rate(sample_rate)
        mono = as_mono_f32(samples)
        demo = resolve_rnnoise_demo()
        if mono.size == 0:
            return mono

        pcm = _float_to_s16(mono)
        pad = (-pcm.size) % FRAME_SAMPLES_A
        if pad:
            pcm = np.concatenate([pcm, np.zeros(pad, dtype=np.int16)])

        with tempfile.TemporaryDirectory(prefix="call_nr_rnnoise_") as tmp:
            raw_in = Path(tmp) / "in.raw"
            raw_out = Path(tmp) / "out.raw"
            raw_in.write_bytes(pcm.tobytes())
            try:
                subprocess.run(
                    [str(demo), str(raw_in), str(raw_out)],
                    check=True,
                    capture_output=True,
                )
            except subprocess.CalledProcessError as exc:
                err = (exc.stderr or b"").decode("utf-8", "replace")
                raise RuntimeError(f"rnnoise_demo failed (rc={exc.returncode}): {err}") from exc
            if not raw_out.is_file() or raw_out.stat().st_size == 0:
                raise RuntimeError(f"rnnoise_demo produced empty output: {raw_out}")
            decoded = np.frombuffer(raw_out.read_bytes(), dtype="<i2").copy()

        restored = _s16_to_float(decoded)[: mono.size]
        if restored.size < mono.size:
            restored = np.pad(restored, (0, mono.size - restored.size))
        return np.ascontiguousarray(restored, dtype=np.float32)
