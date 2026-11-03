# SPDX-License-Identifier: Apache-2.0
"""Desktop audition helper for filter-listen. Gradio is not required in CI."""

from __future__ import annotations

import array
import ast
import importlib.util
import json
import math
import subprocess
import sys
import wave
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "algo" / "filter-listen"
SCRIPT = MODULE / "scripts" / "audition_ui.py"
APPLY = MODULE / "scripts" / "apply_peq_wav.py"
README = MODULE / "README.md"
WORKFLOWS = ROOT / ".github" / "workflows"
SINE = MODULE / "testdata" / "sine_1k_0p5s.wav"
SILENCE = MODULE / "testdata" / "silence_0p5s.wav"
BAND_KEYS = {"fc", "Q", "gain", "type"}

if str(MODULE) not in sys.path:
    sys.path.insert(0, str(MODULE))

import audition as audition_mod
from audition import (
    UI_PRESETS,
    audition,
    load_preset,
    preset_path,
)


def _load_ui():
    spec = importlib.util.spec_from_file_location("filter_listen_audition_ui", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _tone(path: Path, freq: float, scale: float, sample_rate: int = 48000, seconds: float = 0.05) -> Path:
    count = int(sample_rate * seconds)
    pcm = array.array("h")
    for index in range(count):
        sample = scale * math.sin(2.0 * math.pi * freq * index / sample_rate)
        clipped = max(-1.0, min(1.0, sample))
        pcm.append(round(clipped * 32767.0))
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(pcm.tobytes())
    return path


def _rms(path: Path) -> float:
    spec = importlib.util.spec_from_file_location("filter_listen_apply_for_rms", APPLY)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    samples, _rate = module.read_wav_mono(path)
    if not samples:
        return 0.0
    return math.sqrt(sum(sample * sample for sample in samples) / len(samples))


def _apply_cli(src: Path, peq: Path, dest: Path) -> None:
    subprocess.run(
        [
            sys.executable,
            str(APPLY),
            "--wav",
            str(src),
            "--peq",
            str(peq),
            "-o",
            str(dest),
        ],
        check=True,
        capture_output=True,
        text=True,
    )


def test_ui_preset_list_is_the_stdlib_set():
    assert UI_PRESETS == (
        "passthrough",
        "lowpass",
        "highpass",
        "peaking",
        "example_compensation",
    )
    assert "autoeq" not in UI_PRESETS


def test_presets_match_peq_schema_types_without_editing_schema():
    schema = json.loads((MODULE / "configs" / "peq_schema.json").read_text(encoding="utf-8"))
    enum = schema["properties"]["bands"]["items"]["properties"]["type"]["enum"]
    assert schema["required"] == ["sample_rate", "bands"]
    assert "audition" not in schema["$id"]
    kinds = {
        "passthrough": set(),
        "lowpass": {"lowpass"},
        "highpass": {"highpass"},
        "peaking": {"peaking"},
        "example_compensation": {"lowshelf", "peaking", "highshelf"},
    }
    for name in UI_PRESETS:
        doc = load_preset(name)
        assert doc["sample_rate"] == 48000
        assert isinstance(doc["bands"], list)
        seen = set()
        for band in doc["bands"]:
            assert set(band) == BAND_KEYS
            assert band["type"] in enum
            assert band["fc"] > 0
            assert band["Q"] > 0
            seen.add(band["type"])
        assert seen == kinds[name]
        assert (doc.get("meta") or {}).get("generator") != "autoeq"
    assert preset_path("example_compensation").name == "example_compensation.json"
    assert len(load_preset("peaking")["bands"]) >= 1
    assert load_preset("lowpass")["bands"][0]["gain"] == 0.0
    assert load_preset("passthrough")["bands"] == []


def test_passthrough_matches_apply_cli_and_keeps_original(tmp_path: Path):
    result = audition(None, str(SINE), "passthrough", out_dir=tmp_path / "out")
    assert result.ok, result.message
    assert result.input_wav is not None and result.output_wav is not None
    assert Path(result.input_wav).read_bytes() == SINE.read_bytes()
    cli_out = tmp_path / "cli.wav"
    _apply_cli(SINE, preset_path("passthrough"), cli_out)
    assert Path(result.output_wav).read_bytes() == cli_out.read_bytes()
    with wave.open(result.output_wav, "rb") as handle:
        assert handle.getframerate() == 48000
        assert handle.getnchannels() == 1
        assert handle.getsampwidth() == 2
        assert handle.getnframes() == 24000
    assert "preset=passthrough" in result.message
    assert "peq_bands=0" in result.message
    assert "非听感定稿" in result.message
    assert "不宣称评测准入" in result.message
    assert "exit 3" not in result.message
    assert "exit 2" not in result.message


def test_named_presets_match_apply_cli_and_change_the_sine(tmp_path: Path):
    passthrough = audition(None, str(SINE), "passthrough", out_dir=tmp_path / "pass")
    assert passthrough.ok, passthrough.message
    base = _rms(Path(passthrough.output_wav))
    assert base > 0.01
    for name, bands in (("lowpass", 1), ("highpass", 1), ("peaking", 2), ("example_compensation", 5)):
        result = audition(None, str(SINE), name, out_dir=tmp_path / name)
        assert result.ok, result.message
        assert f"preset={name}" in result.message
        assert f"peq_bands={bands}" in result.message
        cli_out = tmp_path / f"{name}-cli.wav"
        _apply_cli(SINE, preset_path(name), cli_out)
        assert Path(result.output_wav).read_bytes() == cli_out.read_bytes()
        level = _rms(Path(result.output_wav))
        if name in ("lowpass", "highpass"):
            assert level < base * 0.5
        elif name == "peaking":
            assert level > base * 1.5
        else:
            assert level != pytest.approx(base, rel=0.02)


def test_silence_stays_silent(tmp_path: Path):
    result = audition(None, str(SILENCE), "lowpass", out_dir=tmp_path / "out")
    assert result.ok, result.message
    with wave.open(result.output_wav, "rb") as handle:
        raw = handle.readframes(handle.getnframes())
    assert not any(raw)


def test_non_48k_input_is_resampled_on_the_graph_path(tmp_path: Path):
    src = _tone(tmp_path / "in.wav", 440.0, 0.2, sample_rate=16000, seconds=0.1)
    result = audition(None, str(src), "passthrough", out_dir=tmp_path / "out")
    assert result.ok, result.message
    with wave.open(result.output_wav, "rb") as handle:
        assert handle.getframerate() == 48000
        assert handle.getnframes() == round(1600 * 48000 / 16000)
    assert "in_sr=16000" in result.message


def test_local_path_wins_over_upload(tmp_path: Path):
    uploaded = _tone(tmp_path / "upload.wav", 440.0, 0.1)
    local = _tone(tmp_path / "local.wav", 440.0, 0.4)
    result = audition(str(uploaded), str(local), "passthrough", out_dir=tmp_path / "out")
    assert result.ok, result.message
    cli_local = tmp_path / "cli-local.wav"
    cli_upload = tmp_path / "cli-upload.wav"
    _apply_cli(local, preset_path("passthrough"), cli_local)
    _apply_cli(uploaded, preset_path("passthrough"), cli_upload)
    rendered = Path(result.output_wav).read_bytes()
    assert rendered == cli_local.read_bytes()
    assert rendered != cli_upload.read_bytes()


def test_gradio_dict_upload_is_accepted(tmp_path: Path):
    src = _tone(tmp_path / "in.wav", 1000.0, 0.15)
    result = audition({"path": str(src)}, "  ", "passthrough", out_dir=tmp_path / "out")
    assert result.ok, result.message
    assert Path(result.output_wav).is_file()
    assert Path(result.input_wav).read_bytes() == src.read_bytes()


def test_missing_path_is_exit_2_and_ignores_upload(tmp_path: Path):
    src = _tone(tmp_path / "in.wav", 440.0, 0.1)
    missing = audition(str(src), str(tmp_path / "nope.wav"), "passthrough", out_dir=tmp_path / "out")
    assert missing.ok is False
    assert missing.output_wav is None
    assert missing.input_wav is None
    assert missing.message.startswith("exit 2")
    assert "exit 3" not in missing.message
    assert "nope.wav" in missing.message
    empty = audition(None, "  ", "passthrough", out_dir=tmp_path / "out")
    assert empty.ok is False
    assert empty.message.startswith("exit 2")
    assert "upload a WAV" in empty.message


def test_unreadable_wav_is_exit_2(tmp_path: Path):
    text = tmp_path / "notes.txt"
    text.write_text("not a wav", encoding="utf-8")
    result = audition(None, str(text), "passthrough", out_dir=tmp_path / "out")
    assert result.ok is False
    assert result.output_wav is None
    assert result.message.startswith("exit 2")

    eight = tmp_path / "eight.wav"
    with wave.open(str(eight), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(1)
        handle.setframerate(48000)
        handle.writeframes(bytes([128, 140, 160, 128]))
    narrow = audition(None, str(eight), "lowpass", out_dir=tmp_path / "out8")
    assert narrow.ok is False
    assert narrow.message.startswith("exit 2")
    assert "16-bit" in narrow.message


def test_unknown_preset_is_exit_2(tmp_path: Path):
    result = audition(None, str(SINE), "not-a-preset", out_dir=tmp_path / "out")
    assert result.ok is False
    assert result.output_wav is None
    assert result.input_wav is not None and Path(result.input_wav).is_file()
    assert result.message.startswith("exit 2")
    assert "unknown filter preset" in result.message
    blank = audition(None, str(SINE), "  ", out_dir=tmp_path / "blank")
    assert blank.ok is False
    assert blank.message.startswith("exit 2")


def test_broken_preset_json_is_exit_2(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(audition_mod, "CONFIG_DIR", tmp_path)
    (tmp_path / "audition_lowpass.json").write_text("{", encoding="utf-8")
    result = audition(None, str(SINE), "lowpass", out_dir=tmp_path / "out")
    assert result.ok is False
    assert result.output_wav is None
    assert result.input_wav is not None
    assert result.message.startswith("exit 2")
    assert "unreadable preset" in result.message


def test_autoeq_preset_missing_is_exit_3(monkeypatch, tmp_path: Path):
    if importlib.util.find_spec("autoeq") is not None:
        pytest.skip("autoeq is importable; unit tests do not require it")
    configs = tmp_path / "configs"
    configs.mkdir()
    (configs / "needs_autoeq.json").write_text(
        json.dumps(
            {
                "name": "needs_autoeq",
                "sample_rate": 48000,
                "preamp_db": 0.0,
                "bands": [{"fc": 1000.0, "Q": 1.0, "gain": 1.0, "type": "peaking"}],
                "meta": {"generator": "autoeq"},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(audition_mod, "CONFIG_DIR", configs)
    monkeypatch.setitem(audition_mod.PRESET_FILES, "needs_autoeq", "needs_autoeq.json")
    result = audition(None, str(SINE), "needs_autoeq", out_dir=tmp_path / "out")
    assert result.ok is False
    assert result.output_wav is None
    assert result.input_wav is not None and Path(result.input_wav).is_file()
    assert result.message.startswith("exit 3")
    assert "autoeq" in result.message.lower()
    assert "pip install autoeq" in result.message
    assert "不宣称评测准入" in result.message
    assert "vendor" in result.message.lower()


def test_readme_launch_and_ui_requirements_stay_out_of_ci():
    text = README.read_text(encoding="utf-8")
    assert "pip install -r algo/filter-listen/requirements-ui.txt" in text
    assert "python algo/filter-listen/scripts/audition_ui.py" in text
    assert "127.0.0.1:7860" in text
    assert "非听感定稿" in text
    assert "不宣称评测准入" in text
    assert "peq_schema.json" in text
    assert "exit 2" in text
    assert "exit 3" in text
    requirements = (MODULE / "requirements-ui.txt").read_text(encoding="utf-8")
    assert "gradio>=4.44" in requirements
    assert "-r requirements.txt" in requirements
    base = (MODULE / "requirements.txt").read_text(encoding="utf-8")
    for line in base.splitlines():
        code = line.split("#", 1)[0]
        assert "gradio" not in code.lower()
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
    helper = ast.parse((MODULE / "audition.py").read_text(encoding="utf-8"))
    for node in ast.walk(helper):
        if isinstance(node, ast.Import):
            assert all(alias.name != "gradio" for alias in node.names)
        if isinstance(node, ast.ImportFrom):
            assert node.module != "gradio"


def test_main_reports_missing_gradio(capsys):
    ui = _load_ui()

    def boom():
        raise ImportError("No module named 'gradio'")

    ui.build_demo = boom
    assert ui.main([]) == 1
    captured = capsys.readouterr()
    assert "algo/filter-listen/requirements-ui.txt" in captured.err
    assert "not part of CI" in captured.err


def test_audition_page_serves_locally():
    pytest.importorskip("gradio")
    ui = _load_ui()
    demo = ui.build_demo()
    _, local_url, _ = demo.launch(
        server_name="127.0.0.1",
        server_port=7871,
        prevent_thread_lock=True,
        share=False,
        quiet=True,
        show_error=True,
    )
    try:
        import urllib.request

        html = urllib.request.urlopen(local_url, timeout=30).read().decode("utf-8", "replace")
        assert "filter-listen" in html
    finally:
        demo.close()
