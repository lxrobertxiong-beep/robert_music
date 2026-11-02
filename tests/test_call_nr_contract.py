"""Contract shape and identity framing. Synthetic audio only; no admission numbers."""

from __future__ import annotations

import importlib.util

import numpy as np
import pytest
import soundfile as sf
from call_nr.backends import deepfilternet as dfn
from call_nr.backends import get_backend, rnnoise
from call_nr.contract import (
    CONTRACT_A,
    CONTRACT_A_ID,
    CONTRACT_B,
    CONTRACT_B_ID,
    FRAME_SAMPLES_A,
    FRAME_SAMPLES_B,
    SAMPLE_RATE_A,
    SAMPLE_RATE_B,
)
from call_nr.io import downsample_48_to_16, read_wav, upsample_16_to_48, write_wav
from call_nr.pipeline import BackendUnavailable, IdentityBackend, PassThroughBackend


def test_contracts_are_distinct_and_only_a_is_implemented():
    assert CONTRACT_A.id == CONTRACT_A_ID == "A_48k_480"
    assert CONTRACT_A.sample_rate_hz == SAMPLE_RATE_A == 48_000
    assert CONTRACT_A.frame_samples == FRAME_SAMPLES_A == 480
    assert CONTRACT_A.implemented is True
    assert CONTRACT_B.id == CONTRACT_B_ID == "B_16k_256"
    assert CONTRACT_B.sample_rate_hz == SAMPLE_RATE_B == 16_000
    assert CONTRACT_B.frame_samples == FRAME_SAMPLES_B == 256
    assert CONTRACT_B.implemented is False


def test_identity_preserves_unaligned_length_and_samples():
    backend = IdentityBackend()
    assert backend.lookahead_frames == 0
    sample_rate = SAMPLE_RATE_A
    count = FRAME_SAMPLES_A * 2 + 50
    time = np.arange(count, dtype=np.float32) / sample_rate
    original = (0.25 * np.sin(2 * np.pi * 440 * time)).astype(np.float32)
    backend.reset()
    rendered = backend.process(original, sample_rate)
    assert rendered.shape == original.shape
    assert rendered.dtype == np.float32
    assert np.array_equal(rendered, original)


def test_identity_frame_and_rate_guards():
    backend = IdentityBackend()
    frame = np.linspace(-0.5, 0.5, FRAME_SAMPLES_A, dtype=np.float32)
    assert np.array_equal(backend.process_frame(frame), frame)
    with pytest.raises(ValueError, match="480"):
        backend.process_frame(np.zeros(FRAME_SAMPLES_B, dtype=np.float32))
    with pytest.raises(ValueError, match=CONTRACT_A_ID):
        backend.process(np.zeros(FRAME_SAMPLES_B, dtype=np.float32), SAMPLE_RATE_B)
    assert backend.process(np.zeros(0, dtype=np.float32), SAMPLE_RATE_A).size == 0


def test_passthrough_alias_matches_identity():
    original = np.arange(FRAME_SAMPLES_A + 3, dtype=np.float32) / 1000
    identity = get_backend("identity").process(original, SAMPLE_RATE_A)
    passed = get_backend("passthrough").process(original, SAMPLE_RATE_A)
    assert isinstance(get_backend("passthrough"), PassThroughBackend)
    assert np.array_equal(identity, passed)
    with pytest.raises(ValueError, match="unknown backend"):
        get_backend("no-such-backend")


def test_wav_downmix_and_float_roundtrip(tmp_path):
    stereo = np.array([[1.0, -1.0], [0.5, 0.5]], dtype=np.float32)
    path = tmp_path / "stereo.wav"
    sf.write(str(path), stereo, SAMPLE_RATE_A, subtype="FLOAT", format="WAV")
    mono, sample_rate = read_wav(path)
    assert sample_rate == SAMPLE_RATE_A
    assert np.allclose(mono, np.array([0.0, 0.5], dtype=np.float32))

    tone = np.array([0.1, -0.2, 0.3], dtype=np.float32)
    dest = tmp_path / "mono.wav"
    write_wav(dest, tone, SAMPLE_RATE_A)
    loaded, loaded_rate = read_wav(dest)
    assert loaded_rate == SAMPLE_RATE_A
    assert np.allclose(loaded, tone, atol=1e-6)


def test_soxr_constant_roundtrip_16_48():
    pytest.importorskip("soxr")
    original = np.full(1600, 0.25, dtype=np.float32)
    up = upsample_16_to_48(original)
    assert up.dtype == np.float32
    assert abs(len(up) / len(original) - 3.0) < 0.05
    down = downsample_48_to_16(up)
    middle = down[300:-300]
    assert middle.size > 0
    assert np.max(np.abs(middle - 0.25)) < 1e-3


def test_rnnoise_missing_backend_is_explicit(monkeypatch):
    monkeypatch.delenv("RNNOISE_DEMO", raising=False)
    monkeypatch.delenv("RNNOISE_ROOT", raising=False)
    monkeypatch.setattr(rnnoise, "_candidate_roots", list)
    with pytest.raises(BackendUnavailable, match="RNNoise"):
        rnnoise.RNNoiseBackend().process(np.zeros(FRAME_SAMPLES_A, dtype=np.float32), SAMPLE_RATE_A)
    monkeypatch.setenv("RNNOISE_DEMO", "/no/such/rnnoise_demo")
    with pytest.raises(BackendUnavailable, match="not an executable"):
        rnnoise.resolve_rnnoise_demo()


def test_rnnoise_rejects_contract_b_before_looking_up_a_binary():
    with pytest.raises(ValueError, match=CONTRACT_A_ID):
        rnnoise.RNNoiseBackend().process(np.zeros(FRAME_SAMPLES_B, dtype=np.float32), SAMPLE_RATE_B)


def test_deepfilternet_pin_and_missing_extra():
    assert dfn.MODEL_NAME == "DeepFilterNet3"
    assert dfn.PYPI_PIN == "deepfilternet==0.5.6"
    assert dfn.UPSTREAM_COMMIT.startswith("978576aa")
    assert dfn.DeepFilterNetBackend().lookahead_frames is None
    if importlib.util.find_spec("df") is None:
        with pytest.raises(BackendUnavailable, match="DeepFilterNet3"):
            dfn.DeepFilterNetBackend().process(
                np.zeros(FRAME_SAMPLES_A, dtype=np.float32),
                SAMPLE_RATE_A,
            )
        return
    pytest.skip("deepfilternet is importable; unit tests do not download weights")
