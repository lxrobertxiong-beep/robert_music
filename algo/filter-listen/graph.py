# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 daopeng xiong and contributors
"""M2 audio graph stubs: 48 kHz / 10 ms path.

Pipeline:
  in → [boundary resample to 48k] → [optional call AEC/NS insert] → [PEQ] → [soft limiter] → out

No vendor libraries. The call insert point is intentionally unused in M2.
The soft limiter is an engineering stub and is not a listening-test sign-off
(非听感定稿).
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from peq import PeqCascade, peq_from_dict


def _as_floats(samples: Sequence[float]) -> list[float]:
    return [float(sample) for sample in samples]


def _linear_resample(samples: Sequence[float], n_out: int) -> list[float]:
    """Linear interpolation stub (endpoint=False index mapping). Not production SRC."""
    block = _as_floats(samples)
    n_in = len(block)
    if n_in < 2 or n_out < 1:
        return [0.0] * max(n_out, 0)
    output: list[float] = []
    for index in range(n_out):
        position = (index / n_out) * n_in
        left = int(position)
        if left >= n_in - 1:
            output.append(block[-1])
            continue
        frac = position - left
        output.append(block[left] * (1.0 - frac) + block[left + 1] * frac)
    return output


@dataclass
class GraphConfig:
    sample_rate: int = 48000
    frame_samples: int = 480  # 10 ms @ 48 kHz
    latency_budget_ms: float = 10.0
    enable_call_insert: bool = False
    limiter_threshold: float = 0.98
    peq: Mapping[str, Any] | None = None


@dataclass
class AudioGraph:
    """Frame-based processing graph (working PEQ + soft-limiter stub)."""

    config: GraphConfig = field(default_factory=GraphConfig)
    peq: PeqCascade | None = None
    call_insert: Callable[[Sequence[float]], Sequence[float]] | None = None
    _resample_hook: Callable[[Sequence[float], int, int], Sequence[float]] | None = None

    def __post_init__(self) -> None:
        if self.peq is None and self.config.peq is not None:
            self.peq = peq_from_dict(self.config.peq, sample_rate=self.config.sample_rate)
        elif self.peq is None:
            self.peq = PeqCascade([], sample_rate=self.config.sample_rate)

    def set_resample_hook(
        self,
        fn: Callable[[Sequence[float], int, int], Sequence[float]],
    ) -> None:
        """Boundary resample: (x, src_sr, dst_sr) -> y. Host provides a real resampler."""
        self._resample_hook = fn

    def resample_boundary(self, samples: Sequence[float], src_sr: int) -> list[float]:
        """Resample to the graph sample rate. Identity when rates match."""
        dst = self.config.sample_rate
        if src_sr == dst:
            return _as_floats(samples)
        if self._resample_hook is not None:
            return _as_floats(self._resample_hook(samples, src_sr, dst))
        n_out = round(len(samples) * dst / float(src_sr))
        return _linear_resample(samples, n_out)

    def call_insert_point(self, frame: Sequence[float]) -> list[float]:
        """Optional AEC/NS insert. Unused in M2 when enable_call_insert is False."""
        block = _as_floats(frame)
        if not self.config.enable_call_insert or self.call_insert is None:
            return block
        return _as_floats(self.call_insert(block))

    def soft_limiter(self, frame: Sequence[float]) -> list[float]:
        """Tanh soft clip toward limiter_threshold.

        Engineering stand-in for mblimiter/DRC. 非听感定稿 — not a listening curve.
        """
        threshold = float(self.config.limiter_threshold)
        block = _as_floats(frame)
        if threshold <= 0:
            return block
        return [threshold * math.tanh(sample / threshold) for sample in block]

    def process_frame(self, frame: Sequence[float]) -> list[float]:
        """One 10 ms frame at 48 kHz after the boundary resample."""
        output = self.call_insert_point(frame)
        assert self.peq is not None
        output = self.peq.process_frame(output)
        return self.soft_limiter(output)

    def process_buffer(
        self,
        samples: Sequence[float],
        src_sr: int | None = None,
    ) -> list[float]:
        """Full buffer: optional resample, then a frame walk."""
        sr = self.config.sample_rate if src_sr is None else int(src_sr)
        block = self.resample_boundary(samples, sr)
        frame_size = self.config.frame_samples
        output = [0.0] * len(block)
        for start in range(0, len(block), frame_size):
            end = min(start + frame_size, len(block))
            chunk = block[start:end]
            if end - start < frame_size:
                padded = [0.0] * frame_size
                padded[: end - start] = chunk
                processed = self.process_frame(padded)[: end - start]
            else:
                processed = self.process_frame(chunk)
            output[start:end] = processed
        return output

    def describe(self) -> dict[str, Any]:
        return {
            "sample_rate": self.config.sample_rate,
            "frame_samples": self.config.frame_samples,
            "latency_budget_ms": self.config.latency_budget_ms,
            "enable_call_insert": self.config.enable_call_insert,
            "n_peq_bands": 0 if self.peq is None else len(self.peq.filters),
            "limiter_threshold": self.config.limiter_threshold,
        }
