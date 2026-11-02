"""Desktop launcher for the control stub. Does not execute jobs."""

from __future__ import annotations

import importlib.util
import os
import socket
import subprocess
import time
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DESKTOP = ROOT / "control" / "desktop"
DESKTOP_FILE = DESKTOP / "robert-music-control-stub.desktop"


def _load_launcher():
    spec = importlib.util.spec_from_file_location(
        "control_launch_stub", DESKTOP / "launch_stub.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _split_exec(value: str) -> list[str]:
    """Split a Desktop Entry Exec value. Enough for this repo's entry."""
    args: list[str] = []
    buf: list[str] = []
    quote = False
    escape = False
    for ch in value:
        if escape:
            buf.append(ch)
            escape = False
        elif ch == "\\":
            escape = True
        elif ch == '"':
            quote = not quote
        elif ch == " " and not quote:
            if buf:
                args.append("".join(buf))
                buf = []
        else:
            buf.append(ch)
    if buf:
        args.append("".join(buf))
    return args


def _port_open(port: int = 8765) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.2):
            return True
    except OSError:
        return False


def test_usage_text_lists_cli_examples():
    launcher = _load_launcher()
    text = launcher.usage_text()
    assert "127.0.0.1:8765" in text
    assert "control/README.md" in text or str(launcher.README) in text
    assert "export_peq" in text
    assert "run_eval" in text
    assert "execute=true" in text
    assert "filter-listen" in text
    assert "call-nr" in text
    assert launcher.STUB_SERVER == ROOT / "control" / "stub_server.py"
    assert launcher.REPO_ROOT == ROOT


def test_usage_only_does_not_bind():
    if _port_open():
        # Still must not be our failure; usage-only never binds.
        pass
    env = os.environ.copy()
    env["CONTROL_LAUNCHER_NO_OPEN"] = "1"
    proc = subprocess.run(
        ["python3", str(DESKTOP / "launch_stub.py"), "--usage-only"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert "127.0.0.1:8765" in proc.stdout
    assert "curl -s http://127.0.0.1:8765/v1/plugins" in proc.stdout


def test_desktop_entry_keys():
    text = DESKTOP_FILE.read_text(encoding="utf-8")
    assert "Type=Application" in text
    assert "Terminal=true" in text
    assert "Name=Control stub (local)" in text
    assert "Exec=" in text
    assert "%k" in text
    assert "launch_stub.py" in text
    assert text.endswith("\n")


def test_desktop_exec_usage_only_resolves_sibling():
    exec_line = ""
    for line in DESKTOP_FILE.read_text(encoding="utf-8").splitlines():
        if line.startswith("Exec="):
            exec_line = line[len("Exec=") :]
            break
    assert exec_line
    argv = _split_exec(exec_line)
    argv = [str(DESKTOP_FILE) if arg == "%k" else arg for arg in argv]
    argv.append("--usage-only")
    env = os.environ.copy()
    env["CONTROL_LAUNCHER_NO_OPEN"] = "1"
    proc = subprocess.run(
        argv,
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert "127.0.0.1:8765" in proc.stdout

    uri = "file://" + DESKTOP_FILE.resolve().as_posix()
    argv = _split_exec(exec_line)
    argv = [uri if arg == "%k" else arg for arg in argv]
    argv.append("--usage-only")
    proc = subprocess.run(
        argv,
        cwd="/tmp",
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert str(ROOT / "control" / "README.md") in proc.stdout


def test_install_linux_writes_absolute_exec(tmp_path):
    env = os.environ.copy()
    env["XDG_DATA_HOME"] = str(tmp_path / "share")
    env["HOME"] = str(tmp_path)
    proc = subprocess.run(
        ["bash", str(DESKTOP / "install-linux.sh")],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    installed = tmp_path / "share" / "applications" / "robert-music-control-stub.desktop"
    text = installed.read_text(encoding="utf-8")
    launcher = str(DESKTOP / "launch-stub.sh")
    assert f"Exec={launcher}" in text
    assert f"TryExec={launcher}" in text
    assert f"Path={ROOT}" in text
    assert "%k" not in text.split("Exec=", 1)[1].splitlines()[0]
    validate = subprocess.run(
        ["desktop-file-validate", str(installed)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert validate.returncode == 0, validate.stdout + validate.stderr
    usage = subprocess.run(
        [launcher, "--usage-only"],
        cwd=tmp_path,
        env={**env, "CONTROL_LAUNCHER_NO_OPEN": "1"},
        capture_output=True,
        text=True,
        check=False,
    )
    assert usage.returncode == 0, usage.stderr
    assert "execute=true" in usage.stdout


def test_launcher_starts_stub_and_serves_plugins():
    if _port_open():
        pytest.skip("127.0.0.1:8765 is already in use")
    env = os.environ.copy()
    env["CONTROL_LAUNCHER_NO_OPEN"] = "1"
    proc = subprocess.Popen(
        ["bash", str(DESKTOP / "launch-stub.sh")],
        cwd="/tmp",
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    body = ""
    try:
        deadline = time.time() + 5
        while time.time() < deadline:
            if proc.poll() is not None:
                out = proc.stdout.read() if proc.stdout else ""
                raise AssertionError(f"launcher exited early: {out}")
            try:
                with urllib.request.urlopen(
                    "http://127.0.0.1:8765/v1/plugins", timeout=0.3
                ) as resp:
                    body = resp.read().decode("utf-8")
                    break
            except OSError:
                time.sleep(0.1)
        else:
            raise AssertionError("stub did not answer /v1/plugins")
        assert "filter-listen" in body
        assert "call-nr" in body
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=3)
