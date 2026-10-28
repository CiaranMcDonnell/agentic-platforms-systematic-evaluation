#!/usr/bin/env bash
# Build the anonymised artifact zip for the FormaliSE 2027 submission.
#
# Contents: harness source, platform config, scenario definitions, prompts,
# Gherkin files, pyproject/lockfile, an artifact README, and the reported
# executions (CSV + per-stage JSON). Author fields are stripped from scenario
# YAML, and every file is grepped for identifying strings before zipping.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../../.." && pwd)"
OUT="$HERE/desmet-artifact.zip"
STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT

cd "$REPO"
git archive --format=tar HEAD \
  src/desmet config/platforms.yaml data/stories data/prompts data/gherkin \
  pyproject.toml uv.lock \
  | tar -x -C "$STAGE"

# Scenario YAML carries an author field; drop it.
find "$STAGE/data/stories" -name '*.yaml' -exec sed -i '/^author:/d' {} +

mkdir -p "$STAGE/results"
cp "$HERE/results-reported.csv" "$HERE/results-stages.csv" "$STAGE/results/"
cp "$REPO/docs/paper/data/reported-runs.json" "$REPO/docs/paper/data/summary.json" \
   "$REPO/docs/paper/data/summarise.py" "$STAGE/results/"
# Per-stage JSON for each reported execution (file names from the stages_file
# column; the CSV carries no local paths).
uv run --quiet python - "$HERE/results-reported.csv" "$REPO/results/logs" "$STAGE/results" <<'PY'
import csv, shutil, sys
from pathlib import Path
rows = list(csv.DictReader(open(sys.argv[1], newline="", encoding="utf-8")))
logs, out = Path(sys.argv[2]), Path(sys.argv[3])
missing = 0
for r in rows:
    found = list(logs.rglob(r["stages_file"])) if r["stages_file"] else []
    if len(found) == 1:
        dst = out / "stages" / found[0].name
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(found[0], dst)
    else:
        missing += 1
        print(f"stage file for {r['execution_id']}: {len(found)} matches", file=sys.stderr)
sys.exit(1 if missing else 0)
PY

cp "$HERE/README-ARTIFACT.md" "$STAGE/README.md"

# Redact identifying strings: the pyproject authors entry, and the GitHub
# account / deploy repository that git-push output embeds in stage JSON.
sed -i '/name = "Ciaran McDonnell"/d' "$STAGE/pyproject.toml"
grep -rlE 'CiaranMcDonnell|Ciaran McDonnell|ciaran\.mcdonnell|ucdconnect' "$STAGE" | while read -r f; do
  sed -i -E 's#github\.com/CiaranMcDonnell/desmet-deploy#github.com/ANON/deploy-target#g; s/CiaranMcDonnell?/ANON/g; s/Ciaran McDonnell/ANON/g; s/ciaran\.mcdonnell@ucdconnect\.ie/anon@example.org/g; s/ucdconnect/example/g; s/[Cc]iaran/ANON/g' "$f"
done

# Anonymity gate over every file in the staging tree.
if grep -rEil 'mcdonnell|ciaran|\bucd\b|dublin|ferrari|21320201|csgitlab' "$STAGE" >/dev/null; then
  echo "anonymity: HITS"; grep -rEin 'mcdonnell|ciaran|\bucd\b|dublin|ferrari|21320201|csgitlab' "$STAGE" | head; exit 1
fi
echo "anonymity: clean"

rm -f "$OUT"
uv run --quiet python - "$STAGE" "$OUT" <<'PY'
import sys, zipfile
from pathlib import Path
stage, out = Path(sys.argv[1]), Path(sys.argv[2])
with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
    for p in sorted(stage.rglob("*")):
        if p.is_file():
            z.write(p, p.relative_to(stage).as_posix())
    print(f"{len(z.namelist())} files")
PY
echo "wrote $OUT"
