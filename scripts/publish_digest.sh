#!/usr/bin/env bash
# Owner-operated. The default action validates local data without contacting GitHub.
set -euo pipefail
repo=$(cd "$(dirname "$0")/.." && pwd)
digest=${1:?Usage: scripts/publish_digest.sh DIGEST_JSON [--publish]}
mode=${2:---validate}
if [[ "$mode" != "--validate" && "$mode" != "--publish" ]] || [[ $# -gt 2 ]]; then
  echo "Use --validate or --publish." >&2
  exit 2
fi
digest=$(cd "$(dirname "$digest")" && pwd)/$(basename "$digest")
PYTHONPATH="$repo/backend" "${FINN_PYTHON:-$repo/.venv/bin/python}" - "$digest" <<'PY'
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
from finn.digest import read_digest, stamp
digest = read_digest(Path(sys.argv[1]))
checked = digest["checks"]["holdings_checked"]
if checked == 0:
    raise SystemExit("Refusing a digest with zero checked holdings.")
if datetime.now(timezone.utc) - stamp(digest["generated_at"]) > timedelta(hours=36):
    raise SystemExit("Refusing a digest generated more than 36 hours ago.")
print(f"Digest valid: {checked}/{digest['checks']['holdings_total']} checked, {len(digest['items'])} items")
PY
[[ "$mode" == "--publish" ]] || exit 0
git -C "$repo" fetch origin live-data:refs/remotes/origin/live-data
scratch=$(mktemp -d)
cleanup() {
  git -C "$repo" worktree remove "$scratch" 2>/dev/null || true
}
trap cleanup EXIT
git -C "$repo" worktree add --detach "$scratch" origin/live-data
cp "$digest" "$scratch/digest.json"
git -C "$scratch" add -- digest.json
if git -C "$scratch" diff --cached --quiet; then
  echo "Published digest already matches."
  exit 0
fi
git -C "$scratch" commit -m "Update portfolio digest"
git -C "$scratch" push origin HEAD:refs/heads/live-data
