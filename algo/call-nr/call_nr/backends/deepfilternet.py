"""Optional DeepFilterNet3@v0.5.6 adapter.

Pin: PyPI ``deepfilternet==0.5.6`` and ``deepfilterlib==0.5.6``,
upstream commit ``978576aa8400552a4ce9730838c635aa30db5e61``.
The model argument is always ``DeepFilterNet3`` (not the package default,
which can resolve to DFN2).

This backend is a desktop comparison path. It uses the library's default
look-ahead, so ``lookahead_frames`` is ``None`` — it is not a zero-lookahead
baseline. Delay compensation flags in the upstream CLI only shift the
output; they do not remove that look-ahead. The first call may download
weights. A dedicated venv is recommended: the pin declares ``numpy<2``.
"""

from __future__ import annotations

import numpy as np

from call_nr.contract import CONTRACT_A_ID, SAMPLE_RATE_A, require_contract_a_rate
from call_nr.io import as_mono_f32
from call_nr.pipeline import BackendUnavailable

PYPI_PIN = "deepfilternet==0.5.6"
LIB_PIN = "deepfilterlib==0.5.6"
UPSTREAM_COMMIT = "978576aa8400552a4ce9730838c635aa30db5e61"
MODEL_NAME = "DeepFilterNet3"

_MODEL = None
_STATE = None


def _missing(detail: str) -> BackendUnavailable:
    return BackendUnavailable(
        "DeepFilterNet3 is not importable. Optional pin: "
        f"pip install {PYPI_PIN} {LIB_PIN} "
        f"(upstream {UPSTREAM_COMMIT}). Use a dedicated venv if numpy 2.x "
        f"conflicts with the pin's numpy<2 constraint. The model name must be "
        f"{MODEL_NAME}. Detail: {detail}"
    )


def _load_df():
    """Lazy-init DeepFilterNet3 once per process."""
    global _MODEL, _STATE
    if _MODEL is not None and _STATE is not None:
        return _MODEL, _STATE
    try:
        from df.enhance import init_df
    except Exception as exc:  # pragma: no cover - depends on optional extra
        raise _missing(str(exc)) from exc
    model, state, _suffix = init_df(
        MODEL_NAME,
        config_allow_defaults=True,
        log_file=None,
    )
    _MODEL, _STATE = model, state
    return _MODEL, _STATE


def _match_length(audio: np.ndarray, length: int) -> np.ndarray:
    if audio.size < length:
        return np.pad(audio, (0, length - audio.size))
    return audio[:length]


class DeepFilterNetBackend:
    """Desktop DeepFilterNet3 comparison at contract A. Not the on-device path."""

    name = "deepfilternet"
    contract_id = CONTRACT_A_ID
    lookahead_frames = None

    def reset(self) -> None:
        return None

    def process_frame(self, frame: np.ndarray) -> np.ndarray:
        return self.process(frame, SAMPLE_RATE_A)

    def process(self, samples: np.ndarray, sample_rate: int) -> np.ndarray:
        require_contract_a_rate(sample_rate)
        mono = as_mono_f32(samples)
        if mono.size == 0:
            return mono
        model, state = _load_df()
        try:
            import torch
            from df.enhance import enhance
        except Exception as exc:  # pragma: no cover - optional extra
            raise _missing(str(exc)) from exc
        audio = torch.from_numpy(np.ascontiguousarray(mono)).unsqueeze(0)
        with torch.no_grad():
            enhanced = enhance(model, state, audio, pad=True)
        rendered = enhanced.squeeze(0).detach().cpu().numpy().astype(np.float32)
        return np.ascontiguousarray(_match_length(rendered, mono.size), dtype=np.float32)
