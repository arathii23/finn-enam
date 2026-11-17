# FINN final release rehearsal

Local candidate, 17 Nov 2026 IST. No external state has been changed. The extraction gate chose the subject-line fallback. The portfolio brief uses the original exchange subject and existing category tier, with a primary link where supplied. It does not show a PDF quote, claim a page locator, or lower a tier based on extracted text.

## Phone walkthrough

1. Open the candidate Pages link. Confirm that the brief reports its generation time and the number of holdings checked. If the feed is missing, confirm the explicit replay banner.
2. Open the first material filing. Confirm it leads to the listed NSE attachment. A subject-only card has no page claim. Return and mark the visible batch seen. Reload and verify that the same versions stay acknowledged.
3. Open CERA from the brief. The latest saved scorecard should select standalone September 2026 and identify its older consolidated quarter. Open UltraTech in replay and check that the PBT row opens a comparison with two distinct source links.
4. Open Historical replay. Check the 30 Apr 2025 evidence cutoff, then open an existing saved research brief. Keep one sourced item and reopen the browser to verify that Notebook still has it.
5. For the live path, check PIDILITIND and reject ZZZQX. Record separately when the backend is cold and when local or hosted calls finish.

Stop and resolve any silent source failure, missing source link, cutoff leak, or page that requires desktop interaction. If there is no usable current digest, use the documented replay path and describe it as saved data.

## Claims to verify before drafting an email

| Proposed claim | Evidence now | Release requirement |
|---|---|---|
| First screen shows new exchange notices since the last acknowledged batch | The local digest carries NSE metadata for 15 checked holdings and 28 notices. The local browser rehearsal exercises Seen and reload. | Verify the same flow on the published Pages build and a physical phone. Say subject lines only. |
| Latest results choose the most recent basis | Local September 2026 result for each holding on at least one basis. CERA is standalone that quarter. | Verify the new seed and Pages export are served. Report period and basis. |
| Conflicting figures show both sources | Local UltraTech March 2025 discrepancy. The PDF's currency is unidentified. | Open both sources on the public app. Describe the two numeric values, without assuming equal currency or definitions. |
| Keyless evidence and replay | Local checks in this folder and the dated v2 evaluation. | Verify the new hosted runtime is keyless. Use dated denominators. A test suite and an evaluation are not proof of investment accuracy. |
| Feed cadence, wake time, or phone alerts | Manual digest only. Existing hosted observations are dated. | Omit delivery and cadence claims unless measured on the deployed version. No claim of always-current data. |

The claims audit must use the actual sent email and the approved public build. There is no follow-up email draft for this release candidate.

## Owner-only publication commands

These are prepared instructions for separate approval. Run from the repository root after checking the proposed changes. Keep the user-supplied handoff, private notes, `output/`, database files and transcripts out of the Git commit. The existing snapshot, seed and site links are the rollback points.

### 1. Review and commit code

```bash
git status --short --branch
git diff --check
git config user.name
git config user.email
git add -- .github/workflows/live-prices.yml .github/workflows/digest.yml .github/workflows/eval-fixtures.yml .github/workflows/phone-alerts.yml Dockerfile
git add -- backend/finn/{alerts,api,brief,calendar_feed,cli,current,db,digest,discovery,evaluation,service,snapshot,trust}.py
git add -- backend/finn/sources/{documents,fetch,xbrl}.py
git add -- backend/tests/{test_alerts,test_calendar_feed,test_current,test_digest,test_evaluation,test_m1,test_xbrl,ui_layout}.py
git add -- frontend/src/{AlertsCard,App,CompanyView,DigestView,FinancialsCard,FreshnessLine,QueueView,TrustView,ui}.tsx
git add -- frontend/src/{api,digestApi,lastVisit,links}.ts frontend/src/{research,styles}.css
git add -- scripts/{build_seed.py,make_qr.py,probe_nse_runner.py,publish_digest.sh,run_scheduled_alerts.py}
git add -- docs/FINN_V2_VERIFICATION.md docs/evaluation/2026-11-17/{README.md,eval_report.json,initial_eval_report.json,layout_report.json}
git add -- docs/evaluation/2026-11-17/final/{REHEARSAL.md,gates.json,extraction_spike.json,parity.json,layout_report.json,replay_verification.json,ticker.json}
git diff --cached --name-only
git diff --cached --check
git commit -m "Prepare FINN portfolio review release"
```

Expected: only the named source and approved public evidence files staged. Confirm the repository owner identity and review the staged diff before committing.

### 2. Prepare the upload with the approved commit recorded

```bash
release_dir=/private/tmp/finn-final-seed
release_tag=corpus-2026-11-17
.venv/bin/python - "$release_dir/build_meta.json" "$(git rev-parse HEAD)" <<'PY'
from pathlib import Path
import json, sys
path = Path(sys.argv[1])
meta = json.loads(path.read_text())
meta.update(git_commit=sys.argv[2], working_tree=False)
path.write_text(json.dumps(meta, indent=2) + "\n")
PY
.venv/bin/python scripts/build_seed.py verify --out "$release_dir"
.venv/bin/python scripts/build_seed.py pack --out "$release_dir"
shasum -a 256 "$release_dir/pack/finn.sqlite3" "$release_dir/finn-seed.tar.gz"
git push origin main
gh release create "$release_tag" "$release_dir/finn-seed.tar.gz" --repo arathii23/finn-enam --target "$(git rev-parse HEAD)" \
  --title "Verified FINN corpus 2026-11-17" --notes "NSE primary-source seed for FINN."
```

Only set `working_tree=False` if the approved commit contains the code used for the candidate. The packed manifest should show 84 documents and 212 verified results filing versions for the prepared run. Regenerate an aged digest rather than claiming freshness. A push to main can trigger Render; approve that before the first push. The first code push may still load the old seed. After the release asset is downloadable and the hash matches, update `SEED_URL` in the Dockerfile to `https://github.com/arathii23/finn-enam/releases/download/corpus-2026-11-17/finn-seed.tar.gz`, review and commit only the Dockerfile, and push or deploy through the existing Render settings once approved. Compare `/api/health` and `/api/trust` to the packed manifest. Retain the previous Render deploy and old release.

### 3. Publish the manual digest and matching Pages build

```bash
bash scripts/publish_digest.sh /private/tmp/finn-final-seed/pack/digest.json --validate
bash scripts/publish_digest.sh /private/tmp/finn-final-seed/pack/digest.json --publish
release_dir=/private/tmp/finn-final-seed
static_runtime=$(mktemp -d)
cp "$release_dir/pack/"{finn.sqlite3,SEED_MANIFEST.json,digest.json} "$static_runtime/"
ln -s "$release_dir/pack/sources" "$static_runtime/sources"
asset_dir=$(mktemp -d)
env PYTHONPATH=backend FINN_DATA_DIR="$static_runtime" FINN_MODEL_PROVIDER=keyless \
  .venv/bin/python -m finn export-static --out "$static_runtime/snapshot"
(cd frontend && VITE_STATIC=1 VITE_LIVE_APP_URL=https://finn-mow9.onrender.com \
  VITE_LIVE_PRICES_URL=https://raw.githubusercontent.com/arathii23/finn-enam/live-data/live_prices.json \
  VITE_DIGEST_URL=https://raw.githubusercontent.com/arathii23/finn-enam/live-data/digest.json \
  npm run build -- --base=/finn-enam/ --outDir "$asset_dir")
mkdir -p "$asset_dir/snapshot"
cp -R "$static_runtime/snapshot/." "$asset_dir/snapshot/"
git fetch origin gh-pages:refs/remotes/origin/gh-pages
git rev-parse origin/gh-pages
pages_dir=$(mktemp -d)
git worktree add --detach "$pages_dir" origin/gh-pages
rsync -a --delete "$asset_dir/assets/" "$pages_dir/assets/"
rsync -a --delete "$asset_dir/snapshot/" "$pages_dir/snapshot/"
cp "$asset_dir/index.html" "$pages_dir/index.html"
touch "$pages_dir/.nojekyll"
git -C "$pages_dir" add -- assets snapshot index.html .nojekyll
git -C "$pages_dir" diff --cached --stat
git -C "$pages_dir" commit -m "Publish FINN portfolio review"
git -C "$pages_dir" push origin HEAD:refs/heads/gh-pages
git worktree remove "$pages_dir"
```

The validator refuses zero checked holdings or a digest over 36 hours old. Regenerate locally with an approved current check if needed. Expect the Pages and Render seed hashes to agree, the raw digest to return 200, and both Trust endpoints and the CERA scorecard to return 200. If the Pages bundle fails, revert its publication commit with a normal commit. No schedule or phone alert is needed for the fallback.

### 4. Verify the runner and physical phones

After publication is approved, run `gh workflow run digest.yml --repo arathii23/finn-enam` and capture the run result. That workflow probes access and does not publish. Leave alert delivery dormant. On iOS Safari and Android Chrome, rehearse the steps above. For T1, record five physical-phone runs from open to the correct source, taps and PDF opens, plus the median and maximum. Only draft the follow-up after the claim-to-evidence audit passes.
