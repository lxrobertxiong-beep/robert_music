#!/usr/bin/env python3
"""Start the local control stub and show API/CLI usage.

Desktop entry helper. UI stays API + CLI (decision C): this process prints
curl examples, optionally opens control/README.md, then runs
control/stub_server.py in the foreground on 127.0.0.1:8765.

Jobs stay on the stub's existing dry-run / execute rules.
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

HOST = "127.0.0.1"
PORT = 8765
STUB_URL = f"http://{HOST}:{PORT}"

DESKTOP_DIR = Path(__file__).resolve().parent
CONTROL_DIR = DESKTOP_DIR.parent
REPO_ROOT = CONTROL_DIR.parent
STUB_SERVER = CONTROL_DIR / "stub_server.py"
README = CONTROL_DIR / "README.md"
OPENAPI = CONTROL_DIR / "openapi-stub.yaml"


def usage_text() -> str:
    """Short CLI note. Canonical docs remain control/README.md."""
    export_body = (
        '{"type":"export_peq","plugin_id":"filter-listen","params":'
        '{"fr":"testdata/synthetic_fr.csv","target":"harman_like",'
        '"output":"/tmp/peq.json"}}'
    )
    eval_body = (
        '{"type":"run_eval","plugin_id":"call-nr","params":'
        '{"baseline":"rnnoise"}}'
    )
    lines = [
        "Control stub launcher (UI=C: API + CLI)",
        f"Repo:    {REPO_ROOT}",
        f"Docs:    {README}",
        f"OpenAPI: {OPENAPI}",
        f"Listen:  {STUB_URL}",
        "",
        "This window runs the stub. Close it or press Ctrl+C to stop.",
        "POST /v1/jobs is dry-run unless the URL includes ?execute=true.",
        "execute=true runs only export_peq and pin_version (no weight download).",
        "run_eval with execute=true stays refused.",
        "",
        f"  curl -s {STUB_URL}/v1/plugins",
        f"  curl -s {STUB_URL}/v1/plugins/filter-listen",
        "",
        f"  curl -s -X POST {STUB_URL}/v1/jobs \\",
        "    -H 'Content-Type: application/json' \\",
        f"    -d '{export_body}'",
        "",
        f"  curl -s -X POST {STUB_URL}/v1/jobs \\",
        "    -H 'Content-Type: application/json' \\",
        f"    -d '{eval_body}'",
        "",
        f"  curl -s -X POST '{STUB_URL}/v1/jobs?execute=true' \\",
        "    -H 'Content-Type: application/json' \\",
        f"    -d '{export_body}'",
        "",
    ]
    return "\n".join(lines)


def stub_already_running() -> bool:
    """True when this stub's plugin list answers on the listen port."""
    try:
        with urllib.request.urlopen(f"{STUB_URL}/v1/plugins", timeout=0.4) as resp:
            body = resp.read(8192)
    except (urllib.error.URLError, TimeoutError, OSError):
        return False
    return b"filter-listen" in body and b"call-nr" in body


def port_in_use() -> bool:
    try:
        with socket.create_connection((HOST, PORT), timeout=0.4):
            return True
    except OSError:
        return False


def open_readme() -> None:
    """Best-effort open of the docs. Never raises and never blocks startup."""
    if os.environ.get("CONTROL_LAUNCHER_NO_OPEN") == "1":
        return
    if not README.is_file():
        return
    try:
        if sys.platform.startswith("linux"):
            if not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
                return
            subprocess.Popen(
                ["xdg-open", str(README)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        elif sys.platform == "win32":
            os.startfile(str(README))
        elif sys.platform == "darwin":
            subprocess.Popen(
                ["open", str(README)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
    except (OSError, AttributeError):
        return


def start_server() -> int:
    """Replace this process with the stub (Windows: wait in the same console)."""
    if not STUB_SERVER.is_file():
        print(f"missing stub server: {STUB_SERVER}", file=sys.stderr)
        return 1
    os.chdir(REPO_ROOT)
    argv = [sys.executable, str(STUB_SERVER)]
    if os.name == "nt":
        return int(subprocess.call(argv))
    os.execv(sys.executable, argv)
    return 1


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    usage_only = "--usage-only" in args
    print(usage_text(), end="")
    if not STUB_SERVER.is_file():
        print(f"missing stub server: {STUB_SERVER}", file=sys.stderr)
        return 1
    if usage_only:
        return 0
    open_readme()
    if stub_already_running():
        print(f"Already listening on {STUB_URL}. Not starting a second server.")
        if sys.stdin.isatty():
            try:
                input("Press Enter to close this note. ")
            except EOFError:
                pass
        return 0
    if port_in_use():
        print(
            f"{HOST}:{PORT} is in use and did not answer the control plugin list. "
            "Stop that process, then launch the stub again.",
            file=sys.stderr,
        )
        return 1
    return start_server()


if __name__ == "__main__":
    raise SystemExit(main())
