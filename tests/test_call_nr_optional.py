"""Optional GTCRN and Silero VAD pins fail closed. No weights and no torch."""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
from call_nr.backends import get_backend, gtcrn, silero_vad
from call_nr.contract import (
    CONTRACT_A_ID,
    FRAME_SAMPLES_A,
    FRAME_SAMPLES_B,
    SAMPLE_RATE_A,
    SAMPLE_RATE_B,
)
from call_nr.io import write_wav
from call_nr.pipeline import BackendUnavailable

ROOT = Path(__file__).resolve().parents[1]
INFER = ROOT / "algo" / "call-nr" / "scripts" / "infer.py"
SILERO_CLI = ROOT / "algo" / "call-nr" / "scripts" / "run_silero_vad.py"
README = ROOT / "algo" / "call-nr" / "README.md"
GITIGNORE = ROOT / ".gitignore"

_WEIGHT_ENV = (
    "CALL_NR_GTCRN_WEIGHTS",
    "GTCRN_CHECKPOINT",
    "GTCRN_ROOT",
    "SILERO_VAD_ROOT",
)


def _isolate(monkeypatch: pytest.MonkeyPatch, home: Path) -> None:
    for key in _WEIGHT_ENV:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(gtcrn, "_home", lambda: home)
    monkeypatch.setattr(silero_vad, "_home", lambda: home)


def _clean_subprocess_env(home: Path) -> dict[str, str]:
    env = os.environ.copy()
    for key in _WEIGHT_ENV:
        env.pop(key, None)
    # HOME is redirected so ~/.cache/call-nr cannot satisfy the pin.
    # PYTHONUSERBASE keeps the parent interpreter's user-site (soundfile/soxr)
    # visible after that redirect.
    env["HOME"] = str(home)
    user_base = Path.home() / ".local"
    if user_base.is_dir():
        env["PYTHONUSERBASE"] = str(user_base)
    plugin = str(ROOT / "algo" / "call-nr")
    previous = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = plugin if not previous else plugin + os.pathsep + previous
    return env


def _git_commit(root: Path) -> None:
    subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True, text=True)
    subprocess.run(["git", "add", "."], cwd=root, check=True, capture_output=True, text=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.email=test@example.com",
            "-c",
            "user.name=Pin Test",
            "commit",
            "--no-gpg-sign",
            "-m",
            "pin-test",
        ],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )


def test_readme_and_gitignore_document_local_pins():
    text = README.read_text(encoding="utf-8")
    assert "502ebfab64da7c4a9af78dcb9c6ceef1ebb01c73" in text
    assert "066409f3d9db45a30d21dfcbf9147826ffdd7052" in text
    assert "CALL_NR_GTCRN_WEIGHTS" in text
    assert "GTCRN_CHECKPOINT" in text
    assert "SILERO_VAD_ROOT" in text
    assert ".cache/call-nr" in text
    assert "评测准入" in text
    assert "smoke_missing_weights.sh" in text
    ignored = GITIGNORE.read_text(encoding="utf-8")
    assert "algo/call-nr/third_party/" in ignored
    assert "*.tar" in ignored
    assert "checkpoints/" in ignored
    assert "silero_vad.jit" in ignored


def test_gtcrn_backend_metadata_and_contract_b_guard():
    backend = get_backend("gtcrn")
    assert isinstance(backend, gtcrn.GTCRNBackend)
    assert backend.name == "gtcrn"
    assert backend.contract_id == CONTRACT_A_ID
    assert backend.lookahead_frames is None
    with pytest.raises(ValueError, match=CONTRACT_A_ID):
        backend.process(np.zeros(FRAME_SAMPLES_B, dtype=np.float32), SAMPLE_RATE_B)
    with pytest.raises(ValueError, match="silero_vad"):
        get_backend("silero_vad")


def test_gtcrn_missing_weights_names_the_env_and_pin(monkeypatch, tmp_path: Path):
    _isolate(monkeypatch, tmp_path / "home")
    with pytest.raises(BackendUnavailable, match="CALL_NR_GTCRN_WEIGHTS") as caught:
        gtcrn.GTCRNBackend().process(np.zeros(FRAME_SAMPLES_A, dtype=np.float32), SAMPLE_RATE_A)
    message = str(caught.value)
    assert "model_trained_on_dns3.tar" in message
    assert "502ebfab64da7c4a9af78dcb9c6ceef1ebb01c73" in message
    assert "does not vendor or download" in message


def test_gtcrn_explicit_path_rejects_lfs_pointer(monkeypatch, tmp_path: Path):
    pointer = tmp_path / "model_trained_on_dns3.tar"
    pointer.write_bytes(b"version https://git-lfs.github.com/spec/v1\noid sha256:abc\nsize 1\n")
    monkeypatch.setenv("GTCRN_CHECKPOINT", str(pointer))
    with pytest.raises(BackendUnavailable, match="Git LFS") as caught:
        gtcrn.resolve_gtcrn_weights()
    assert "GTCRN_CHECKPOINT" in str(caught.value)
    assert str(pointer) in str(caught.value)


def test_gtcrn_missing_checkout_after_a_real_sized_file(monkeypatch, tmp_path: Path):
    weights = tmp_path / "model_trained_on_dns3.tar"
    weights.write_bytes(b"x" * 20_000)
    monkeypatch.setenv("CALL_NR_GTCRN_WEIGHTS", str(weights))
    monkeypatch.delenv("GTCRN_ROOT", raising=False)
    monkeypatch.setattr(gtcrn, "_home", lambda: tmp_path / "home")
    with pytest.raises(BackendUnavailable, match="GTCRN_ROOT") as caught:
        gtcrn.GTCRNBackend().process(np.zeros(FRAME_SAMPLES_A, dtype=np.float32), SAMPLE_RATE_A)
    assert "502ebfab" in str(caught.value)
    assert "does not vendor" in str(caught.value)


def test_gtcrn_rejects_a_checkout_that_is_not_the_pin(monkeypatch, tmp_path: Path):
    weights = tmp_path / "model_trained_on_dns3.tar"
    weights.write_bytes(b"x" * 20_000)
    root = tmp_path / "repo"
    root.mkdir()
    (root / "gtcrn.py").write_text("class GTCRN: pass\n", encoding="utf-8")
    _git_commit(root)
    monkeypatch.setenv("CALL_NR_GTCRN_WEIGHTS", str(weights))
    monkeypatch.setenv("GTCRN_ROOT", str(root))
    with pytest.raises(BackendUnavailable, match="502ebfab64da7c4a9af78dcb9c6ceef1ebb01c73"):
        gtcrn.GTCRNBackend().process(np.zeros(FRAME_SAMPLES_A, dtype=np.float32), SAMPLE_RATE_A)


def test_gtcrn_missing_torch_is_explicit(monkeypatch, tmp_path: Path):
    if importlib.util.find_spec("torch") is not None:
        pytest.skip("torch is installed; unit tests do not run real GTCRN")
    weights = tmp_path / "model_trained_on_dns3.tar"
    weights.write_bytes(b"x" * 20_000)
    root = tmp_path / "repo"
    root.mkdir()
    (root / "gtcrn.py").write_text("class GTCRN: pass\n", encoding="utf-8")
    monkeypatch.setenv("CALL_NR_GTCRN_WEIGHTS", str(weights))
    monkeypatch.setenv("GTCRN_ROOT", str(root))
    with pytest.raises(BackendUnavailable, match="torch") as caught:
        gtcrn.GTCRNBackend().process(np.zeros(FRAME_SAMPLES_A, dtype=np.float32), SAMPLE_RATE_A)
    assert "einops" in str(caught.value)
    assert "CI does not install torch" in str(caught.value)


def test_silero_missing_root_names_the_env_and_pin(monkeypatch, tmp_path: Path):
    _isolate(monkeypatch, tmp_path / "home")
    with pytest.raises(BackendUnavailable, match="SILERO_VAD_ROOT") as caught:
        silero_vad.analyze(np.zeros(FRAME_SAMPLES_A, dtype=np.float32), SAMPLE_RATE_A)
    message = str(caught.value)
    assert "066409f3d9db45a30d21dfcbf9147826ffdd7052" in message
    assert "silero_vad.jit" in message
    assert "does not vendor" in message
    assert "torch.hub is not used" in message


def test_silero_explicit_root_rejects_a_tiny_jit(monkeypatch, tmp_path: Path):
    root = tmp_path / "silero-vad"
    (root / "src" / "silero_vad" / "data").mkdir(parents=True)
    (root / "hubconf.py").write_text("def silero_vad(**kwargs):\n    raise RuntimeError('unused')\n", encoding="utf-8")
    jit = root / "src" / "silero_vad" / "data" / "silero_vad.jit"
    jit.write_bytes(b"version https://git-lfs.github.com/spec/v1\n")
    monkeypatch.setenv("SILERO_VAD_ROOT", str(root))
    with pytest.raises(BackendUnavailable, match="Git LFS") as caught:
        silero_vad.resolve_silero_root()
    assert str(root) in str(caught.value)


def test_silero_missing_torch_is_explicit(monkeypatch, tmp_path: Path):
    if importlib.util.find_spec("torch") is not None:
        pytest.skip("torch is installed; unit tests do not run real Silero VAD")
    root = tmp_path / "silero-vad"
    (root / "src" / "silero_vad" / "data").mkdir(parents=True)
    (root / "hubconf.py").write_text("def silero_vad(**kwargs):\n    return None, (None,)\n", encoding="utf-8")
    jit = root / "src" / "silero_vad" / "data" / "silero_vad.jit"
    jit.write_bytes(b"x" * 20_000)
    monkeypatch.setenv("SILERO_VAD_ROOT", str(root))
    with pytest.raises(BackendUnavailable, match="torch") as caught:
        silero_vad.analyze(np.zeros(FRAME_SAMPLES_A, dtype=np.float32), SAMPLE_RATE_A)
    assert "CI does not install torch" in str(caught.value)


def test_cli_optional_backends_exit_3_without_weights(tmp_path: Path):
    count = FRAME_SAMPLES_A
    src = tmp_path / "in.wav"
    write_wav(src, np.zeros(count, dtype=np.float32), SAMPLE_RATE_A)
    env = _clean_subprocess_env(tmp_path / "home")
    gtcrn_out = tmp_path / "out.wav"
    proc = subprocess.run(
        [sys.executable, str(INFER), "--backend", "gtcrn", "-i", str(src), "-o", str(gtcrn_out)],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )
    assert proc.returncode == 3, proc.stderr
    assert "CALL_NR_GTCRN_WEIGHTS" in proc.stderr
    assert "model_trained_on_dns3.tar" in proc.stderr
    assert not gtcrn_out.exists()

    csv_out = tmp_path / "vad_probs.csv"
    proc = subprocess.run(
        [sys.executable, str(INFER), "--backend", "silero_vad", "-i", str(src), "-o", str(csv_out)],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )
    assert proc.returncode == 3, proc.stderr
    assert "SILERO_VAD_ROOT" in proc.stderr
    assert "066409f" in proc.stderr
    assert not csv_out.exists()

    script = subprocess.run(
        [sys.executable, str(SILERO_CLI), "-i", str(src), "-o", str(csv_out)],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )
    assert script.returncode == 3, script.stderr
    assert "silero_vad.jit" in script.stderr
    missing = subprocess.run(
        [sys.executable, str(SILERO_CLI), "-o", str(csv_out)],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )
    assert missing.returncode == 2


def test_smoke_missing_weights_script():
    """The documented shell smoke must observe exit 3 and must not download weights."""
    script = ROOT / "algo" / "call-nr" / "scripts" / "smoke_missing_weights.sh"
    env = os.environ.copy()
    env["PYTHON"] = sys.executable
    for key in _WEIGHT_ENV:
        env.pop(key, None)
    proc = subprocess.run(
        ["bash", str(script)],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "502ebfab64da7c4a9af78dcb9c6ceef1ebb01c73" in proc.stdout
    assert "CALL_NR_GTCRN_WEIGHTS" in proc.stdout
    assert "066409f3d9db45a30d21dfcbf9147826ffdd7052" in proc.stdout
    assert "SILERO_VAD_ROOT" in proc.stdout
    assert "torch.hub is not used" in proc.stdout
    assert "no weights downloaded" in proc.stdout
    if importlib.util.find_spec("torch") is None:
        assert "gtcrn missing torch: exit 3" in proc.stdout
        assert "silero missing torch: exit 3" in proc.stdout
