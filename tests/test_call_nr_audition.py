"""Desktop audition helper. Gradio itself is not required and is not installed in CI."""

from __future__ import annotations

import ast
import importlib.util
from pathlib import Path

import numpy as np
import pytest
from call_nr.audition import UI_BACKENDS, audition
from call_nr.backends import gtcrn, rnnoise
from call_nr.contract import SAMPLE_RATE_A
from call_nr.io import read_wav, write_wav

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "algo" / "call-nr" / "scripts" / "audition_ui.py"
README = ROOT / "algo" / "call-nr" / "README.md"
WORKFLOWS = ROOT / ".github" / "workflows"


def _tone(tmp_path: Path, name: str, scale: float) -> Path:
    count = SAMPLE_RATE_A // 10
    time = np.arange(count, dtype=np.float32) / SAMPLE_RATE_A
    samples = (scale * np.sin(2 * np.pi * 440.0 * time)).astype(np.float32)
    path = tmp_path / name
    write_wav(path, samples, SAMPLE_RATE_A)
    return path


def _load_ui():
    spec = importlib.util.spec_from_file_location("call_nr_audition_ui", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_ui_backend_list_covers_the_waveform_pins():
    assert UI_BACKENDS[:4] == ("identity", "passthrough", "rnnoise", "deepfilternet")
    assert "gtcrn" in UI_BACKENDS
    assert "silero_vad" not in UI_BACKENDS


def test_identity_audition_writes_playable_input_and_output(tmp_path: Path):
    src = _tone(tmp_path, "in.wav", 0.2)
    original, _ = read_wav(src)
    result = audition(None, str(src), "identity", out_dir=tmp_path / "out")
    assert result.ok, result.message
    assert result.output_wav is not None and result.input_wav is not None
    preview, preview_rate = read_wav(result.input_wav)
    rendered, sample_rate = read_wav(result.output_wav)
    assert preview_rate == SAMPLE_RATE_A
    assert sample_rate == SAMPLE_RATE_A
    assert np.allclose(preview, original, atol=1e-6)
    assert np.allclose(rendered, original, atol=1e-6)
    assert "contract=A_48k_480" in result.message
    assert "backend=identity" in result.message
    assert "exit 3" not in result.message


def test_local_path_wins_over_upload(tmp_path: Path):
    uploaded = _tone(tmp_path, "upload.wav", 0.1)
    local = _tone(tmp_path, "local.wav", 0.4)
    result = audition(str(uploaded), str(local), "passthrough", out_dir=tmp_path / "out")
    assert result.ok, result.message
    rendered, _ = read_wav(result.output_wav)
    expected, _ = read_wav(local)
    assert np.allclose(rendered, expected, atol=1e-6)
    assert not np.allclose(rendered, read_wav(uploaded)[0], atol=1e-3)


def test_gradio_dict_upload_is_accepted(tmp_path: Path):
    src = _tone(tmp_path, "in.wav", 0.15)
    result = audition({"path": str(src)}, "  ", "identity", out_dir=tmp_path / "out")
    assert result.ok, result.message
    assert Path(result.output_wav).is_file()


def test_missing_path_is_exit_2_and_ignores_upload(tmp_path: Path):
    src = _tone(tmp_path, "in.wav", 0.1)
    missing = audition(str(src), str(tmp_path / "nope.wav"), "identity", out_dir=tmp_path / "out")
    assert missing.ok is False
    assert missing.output_wav is None
    assert missing.message.startswith("exit 2")
    assert "nope.wav" in missing.message
    empty = audition(None, "  ", "identity", out_dir=tmp_path / "out")
    assert empty.ok is False
    assert empty.message.startswith("exit 2")


def test_rnnoise_missing_is_exit_3_without_raising(monkeypatch, tmp_path: Path):
    monkeypatch.delenv("RNNOISE_DEMO", raising=False)
    monkeypatch.delenv("RNNOISE_ROOT", raising=False)
    monkeypatch.setattr(rnnoise, "_candidate_roots", list)
    src = _tone(tmp_path, "in.wav", 0.1)
    result = audition(str(src), None, "rnnoise", out_dir=tmp_path / "out")
    assert result.ok is False
    assert result.output_wav is None
    assert result.input_wav is not None and Path(result.input_wav).is_file()
    assert result.message.startswith("exit 3")
    assert "RNNOISE_DEMO" in result.message
    assert "904a876dce1f9ab8860c0a5000ed151f9f6eef58" in result.message


def test_gtcrn_missing_names_the_env(monkeypatch, tmp_path: Path):
    for key in ("CALL_NR_GTCRN_WEIGHTS", "GTCRN_CHECKPOINT", "GTCRN_ROOT"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(gtcrn, "_home", lambda: tmp_path / "home")
    src = _tone(tmp_path, "in.wav", 0.1)
    result = audition(None, str(src), "gtcrn", out_dir=tmp_path / "out")
    assert result.ok is False
    assert result.output_wav is None
    assert result.message.startswith("exit 3")
    assert "CALL_NR_GTCRN_WEIGHTS" in result.message
    assert "model_trained_on_dns3.tar" in result.message
    assert "502ebfab64da7c4a9af78dcb9c6ceef1ebb01c73" in result.message


def test_deepfilternet_missing_extra_is_exit_3(tmp_path: Path):
    if importlib.util.find_spec("df") is not None:
        pytest.skip("deepfilternet is importable; unit tests do not download weights")
    src = _tone(tmp_path, "in.wav", 0.1)
    result = audition(str(src), None, "deepfilternet", out_dir=tmp_path / "out")
    assert result.ok is False
    assert result.message.startswith("exit 3")
    assert "deepfilternet==0.5.6" in result.message


def test_readme_launch_and_ui_requirements_stay_out_of_ci():
    text = README.read_text(encoding="utf-8")
    assert "pip install -r algo/call-nr/requirements-ui.txt" in text
    assert "python algo/call-nr/scripts/audition_ui.py" in text
    assert "127.0.0.1:7860" in text
    assert "不是评测准入" in text
    requirements = (ROOT / "algo" / "call-nr" / "requirements-ui.txt").read_text(encoding="utf-8")
    assert "gradio>=4.44" in requirements
    assert "-r requirements.txt" in requirements
    pyproject = (ROOT / "algo" / "call-nr" / "pyproject.toml").read_text(encoding="utf-8")
    assert "gradio>=4.44" in pyproject
    for path in WORKFLOWS.glob("*.yml"):
        for line in path.read_text(encoding="utf-8").splitlines():
            code = line.split("#", 1)[0]
            assert "requirements-ui" not in code
            assert "gradio" not in code.lower()


def test_gradio_import_is_lazy():
    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Import):
            assert all(alias.name != "gradio" for alias in node.names)
        if isinstance(node, ast.ImportFrom):
            assert node.module != "gradio"
    build = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "build_demo")
    found = False
    for node in ast.walk(build):
        if isinstance(node, ast.Import) and any(alias.name == "gradio" for alias in node.names):
            found = True
    assert found


def test_main_reports_missing_gradio(capsys):
    ui = _load_ui()

    def boom():
        raise ImportError("No module named 'gradio'")

    ui.build_demo = boom
    assert ui.main([]) == 1
    captured = capsys.readouterr()
    assert "requirements-ui.txt" in captured.err
    assert "not part of CI" in captured.err


def test_audition_page_serves_locally():
    pytest.importorskip("gradio")
    ui = _load_ui()
    demo = ui.build_demo()
    _, local_url, _ = demo.launch(
        server_name="127.0.0.1",
        server_port=7865,
        prevent_thread_lock=True,
        share=False,
        quiet=True,
        show_error=True,
    )
    try:
        import urllib.request

        html = urllib.request.urlopen(local_url, timeout=30).read().decode("utf-8", "replace")
        assert "call-nr" in html
    finally:
        demo.close()
