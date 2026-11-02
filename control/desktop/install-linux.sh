#!/usr/bin/env bash
# Install a per-user desktop entry that starts this checkout's control stub.
# Rewrites Exec, TryExec, and Path to absolute paths so the menu item keeps
# working after it is copied out of the repository tree.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
SRC="$HERE/robert-music-control-stub.desktop"
LAUNCHER="$HERE/launch-stub.sh"
DEST_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
DEST="$DEST_DIR/robert-music-control-stub.desktop"

if [[ ! -f "$SRC" ]]; then
  echo "missing desktop entry: $SRC" >&2
  exit 1
fi
if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 is required to install the desktop entry" >&2
  exit 1
fi

chmod +x "$LAUNCHER"
mkdir -p "$DEST_DIR"

python3 - "$SRC" "$DEST" "$LAUNCHER" "$REPO" <<'PY'
import pathlib
import sys

src, dest, launcher, repo = sys.argv[1:5]


def quote_desktop(value: str) -> str:
    if any(ch in value for ch in ' \t\n"\\'):
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return value


launcher_field = quote_desktop(launcher)
repo_field = quote_desktop(repo)
out: list[str] = []
saw_path = False
saw_try = False
for line in pathlib.Path(src).read_text(encoding="utf-8").splitlines():
    if line.startswith("Exec="):
        out.append(f"Exec={launcher_field}")
    elif line.startswith("Path="):
        out.append(f"Path={repo_field}")
        saw_path = True
    elif line.startswith("TryExec="):
        out.append(f"TryExec={launcher_field}")
        saw_try = True
    else:
        out.append(line)
if not saw_try:
    out.append(f"TryExec={launcher_field}")
if not saw_path:
    out.append(f"Path={repo_field}")
pathlib.Path(dest).write_text("\n".join(out) + "\n", encoding="utf-8")
PY

chmod 644 "$DEST"
if command -v update-desktop-database >/dev/null 2>&1; then
  update-desktop-database "$DEST_DIR" || true
fi
if command -v xdg-desktop-menu >/dev/null 2>&1; then
  xdg-desktop-menu forceupdate || true
fi

echo "Installed: $DEST"
echo "Menu name: Control stub (local)"
echo "Launcher:  $LAUNCHER"
echo "Remove:    rm -f \"$DEST\""
