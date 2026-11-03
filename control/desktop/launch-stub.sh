#!/usr/bin/env bash
# Start the local control stub from this checkout. Repo-relative: the script
# finds control/desktop/launch_stub.py next to itself, and that module finds
# the repository root. Safe to run from any working directory.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 is required to start control/stub_server.py" >&2
  exit 1
fi

exec python3 "$HERE/launch_stub.py" "$@"
