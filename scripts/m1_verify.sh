#!/usr/bin/env bash
# FINN Milestone 1: one-command setup, real-source ingestion and verification.
# Run on a machine with normal internet access (it downloads from nseindia.com and PyPI/npm):
#   bash scripts/m1_verify.sh
# Every step's output is captured in data/verification/m1_verify.log. Nothing is deployed,
# no paid resource is created, and no model call is made unless OPENAI_API_KEY is set.
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
OUT="$ROOT/data/verification"
mkdir -p "$OUT"
LOG="$OUT/m1_verify.log"
exec > >(tee "$LOG") 2>&1
echo "== FINN M1 verify $(date -u +%Y-%m-%dT%H:%M:%SZ) on $(uname -sm)"

step() { echo; echo "== $1"; }
fail_count=0
run() {
  local rc=0
  "$@" || rc=$?
  if [ "$rc" -ne 0 ]; then
    echo "!! exit $rc: $*"
    fail_count=$((fail_count+1))
  fi
  return "$rc"
}

step "Python environment"
if [ ! -x .venv/bin/python ]; then
  if command -v uv >/dev/null 2>&1; then uv venv --python 3.12 .venv || python3 -m venv .venv
  else "${FINN_PYTHON:-python3}" -m venv .venv; fi
fi
# shellcheck disable=SC1091
. .venv/bin/activate || exit 1
python -c 'import sys; assert sys.version_info >= (3, 10), f"Python 3.10+ required, found {sys.version}"' || { echo "!! Python 3.10+ required (try: brew install python@3.12, or install uv)"; exit 1; }
if command -v uv >/dev/null 2>&1; then
  run uv pip install -q -r backend/requirements-dev.txt || exit 1
else
  run python -m pip install -q -r backend/requirements-dev.txt || exit 1
fi
python -m pip freeze > "$OUT/pip_freeze.txt"
# Keep run() in the parent shell so failed steps are counted accurately.
export PYTHONPATH="$ROOT/backend${PYTHONPATH:+:$PYTHONPATH}"

step "Runtime check (credential presence only; values never printed)"
run python -m finn check-runtime || true

step "Unit/logic tests (synthetic fixtures, mocked network)"
run python -m pytest -q backend/tests || true

step "Frontend build (Vite)"
if command -v npm >/dev/null 2>&1; then
  if run npm --prefix "$ROOT/frontend" install --no-audit --no-fund; then
    run npm --prefix "$ROOT/frontend" run build || true
  else
    echo "Frontend build skipped because package installation failed."
  fi
else
  echo "npm not found: the Vite/TypeScript build remains unverified."
  fail_count=$((fail_count+1))
fi

step "Ingest real sources for INFY (NSE identity, EOD, announcements, FY24 AR, transcripts)"
run python -m finn ingest INFY || true

step "Data checks on the real corpus"
run python -m finn verify --symbol INFY || true

step "Application startup, HTTP smoke and restart persistence"
run python scripts/smoke.py --symbol INFY || true

step "Summary"
echo "steps with non-zero exit: $fail_count"
echo "Reports: $OUT/ingest_report.json, $OUT/m1_checks.json, $OUT/m1_checks.md, $OUT/startup_smoke.json, $LOG"
echo "Start the app:  . .venv/bin/activate && cd backend && python -m finn serve   -> http://127.0.0.1:8000"
if [ "$fail_count" -ne 0 ]; then
  echo "Verification is incomplete or failed; inspect the reports above."
  exit 1
fi
