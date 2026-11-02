#!/usr/bin/env bash
# Short local smoke for GTCRN@502ebfab and Silero VAD@066409f.
# Exit 0 when both pins are on disk and both smokes succeed.
# Exit 3 when weights, the pinned checkout, or torch/einops are missing.
# Does not clone upstream, download weights, or pip-install torch.
# Not an admission result. Same paths as algo/call-nr/README.md.
set -euo pipefail

CALL_NR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO="$(cd "${CALL_NR}/../.." && pwd)"
INFER="${CALL_NR}/scripts/infer.py"
SILERO="${CALL_NR}/scripts/run_silero_vad.py"
MISSING="${CALL_NR}/scripts/smoke_missing_weights.sh"
GTCRN_PIN="502ebfab64da7c4a9af78dcb9c6ceef1ebb01c73"
SILERO_PIN="066409f3d9db45a30d21dfcbf9147826ffdd7052"

usage() {
  cat <<EOF
Usage: check_local_weights_ready.sh [--require | --missing-only]

Default and --require:
  Run the shortest local smoke for GTCRN (${GTCRN_PIN}) and
  Silero VAD (${SILERO_PIN}). Exit 0 when both succeed.
  Exit 3 when weights, the pinned checkout, torch/einops, or the
  identity runtime (numpy, soundfile, soxr) are missing. stderr names
  the gap and the environment variable to set.
  Weight and code search order matches algo/call-nr/README.md:
    CALL_NR_GTCRN_WEIGHTS, GTCRN_CHECKPOINT,
    \$GTCRN_ROOT/checkpoints/model_trained_on_dns3.tar,
    algo/call-nr/third_party/gtcrn, ~/.cache/call-nr/gtcrn/
    Code: GTCRN_ROOT, else third_party/gtcrn, else ~/.cache/call-nr/gtcrn/repo
    (gtcrn.py at the checkout root; git HEAD must be ${GTCRN_PIN})
    SILERO_VAD_ROOT, else third_party/silero-vad, else ~/.cache/call-nr/silero-vad
    (hubconf.py and src/silero_vad/data/silero_vad.jit; git HEAD must be ${SILERO_PIN})

--missing-only:
  Run scripts/smoke_missing_weights.sh. That script asserts a clean tree
  exits 3. When the assertion holds, it exits 0. It does not use local weights.

Does not clone upstream, download weights, or install torch.
不宣称准入. Not an admission result.
Artifacts stay in a temporary directory and are removed on exit.
EOF
}

mode="require"
seen_require=0
seen_missing=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help)
      usage
      exit 0
      ;;
    --require)
      seen_require=1
      if [[ "${seen_missing}" -eq 1 ]]; then
        echo "use only one of --require or --missing-only" >&2
        exit 2
      fi
      mode="require"
      ;;
    --missing-only)
      seen_missing=1
      if [[ "${seen_require}" -eq 1 ]]; then
        echo "use only one of --require or --missing-only" >&2
        exit 2
      fi
      mode="missing-only"
      ;;
    *)
      echo "unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
  shift
done

if [[ "${mode}" == "missing-only" ]]; then
  exec bash "${MISSING}"
fi

if [[ -n "${PYTHON:-}" ]]; then
  PY="${PYTHON}"
elif command -v python3 >/dev/null 2>&1; then
  PY="python3"
else
  PY="python"
fi

print_exit3() {
  cat >&2 <<EOF
check_local_weights_ready: exit 3
Local GTCRN (${GTCRN_PIN}) and Silero VAD (${SILERO_PIN}) are not ready.
The messages above name the missing piece. Set:
  CALL_NR_GTCRN_WEIGHTS or GTCRN_CHECKPOINT
  GTCRN_ROOT to a checkout of ${GTCRN_PIN} with gtcrn.py at the repo root
    (otherwise algo/call-nr/third_party/gtcrn or ~/.cache/call-nr/gtcrn/repo;
     git HEAD must equal the pin when .git is present)
  weights file model_trained_on_dns3.tar
    (also \$GTCRN_ROOT/checkpoints/, third_party, or ~/.cache/call-nr/gtcrn/)
  SILERO_VAD_ROOT to a checkout of ${SILERO_PIN}
    with hubconf.py and src/silero_vad/data/silero_vad.jit
    (otherwise algo/call-nr/third_party/silero-vad or ~/.cache/call-nr/silero-vad)
torch and einops are required before this script can exit 0.
This script does not install them, does not clone upstream, and does not download weights.
torch.hub is not used. 不宣称准入.
EOF
}

if ! command -v "${PY}" >/dev/null 2>&1; then
  echo "Python interpreter not found (${PY})." >&2
  print_exit3
  exit 3
fi

import_err=""
if ! import_err="$("${PY}" -c 'import numpy, soundfile, soxr' 2>&1)"; then
  echo "Missing identity runtime (numpy, soundfile, soxr) or libsndfile." >&2
  if [[ -n "${import_err}" ]]; then
    echo "${import_err}" >&2
  fi
  echo "Install: pip install -r ${REPO}/algo/call-nr/requirements.txt" >&2
  echo "Debian/Ubuntu also needs libsndfile1. This script does not install packages or torch." >&2
  print_exit3
  exit 3
fi

WORK="$(mktemp -d "${TMPDIR:-/tmp}/call-nr-weights-ready.XXXXXX")"
cleanup() { rm -rf "${WORK}"; }
trap cleanup EXIT

if ! "${PY}" - "${WORK}/in.wav" <<'PY'
import sys

import numpy as np
import soundfile as sf

path = sys.argv[1]
sr = 48000
# 0.2 s at 48 kHz. Silero's window is 512 samples at 16 kHz (32 ms);
# GTCRN's STFT is n_fft=512, hop=256 at 16 kHz. This length covers both.
n = 9600
t = np.arange(n, dtype=np.float32) / sr
wav = (0.1 * np.sin(2 * np.pi * 440.0 * t)).astype(np.float32)
sf.write(path, wav, sr, subtype="FLOAT", format="WAV")
PY
then
  echo "could not write the temporary input WAV" >&2
  exit 2
fi

run_smoke() {
  local label="$1"
  local outfile="$2"
  shift 2
  local stdout_file="${WORK}/${label}.stdout"
  local stderr_file="${WORK}/${label}.stderr"
  local code=0
  "$@" >"${stdout_file}" 2>"${stderr_file}" || code=$?
  if [[ "${code}" -eq 0 ]]; then
    if [[ ! -s "${outfile}" ]]; then
      echo "${label}: exit 0 but output is empty: ${outfile}" >&2
      return 1
    fi
    echo "${label}: exit 0"
    cat "${stdout_file}"
    return 0
  fi
  echo "${label}: exit ${code}" >&2
  if [[ -s "${stderr_file}" ]]; then
    cat "${stderr_file}" >&2
  fi
  return "${code}"
}

gtcrn_code=0
run_smoke "gtcrn" "${WORK}/gtcrn.wav" \
  "${PY}" "${INFER}" --backend gtcrn -i "${WORK}/in.wav" -o "${WORK}/gtcrn.wav" \
  || gtcrn_code=$?

silero_code=0
run_smoke "silero_vad" "${WORK}/vad_probs.csv" \
  "${PY}" "${SILERO}" -i "${WORK}/in.wav" -o "${WORK}/vad_probs.csv" \
  || silero_code=$?

if [[ "${gtcrn_code}" -eq 0 && "${silero_code}" -eq 0 ]]; then
  echo "check_local_weights_ready: exit 0"
  echo "Short local smoke finished for GTCRN ${GTCRN_PIN} and Silero VAD ${SILERO_PIN}."
  echo "Temporary outputs were removed. 不宣称准入."
  exit 0
fi

if [[ "${gtcrn_code}" -eq 3 || "${silero_code}" -eq 3 ]]; then
  print_exit3
  exit 3
fi

echo "check_local_weights_ready: unexpected gtcrn=${gtcrn_code} silero_vad=${silero_code}" >&2
if [[ "${gtcrn_code}" -ne 0 ]]; then
  exit "${gtcrn_code}"
fi
exit "${silero_code}"
