#!/usr/bin/env bash
# Compile the FormaliSE paper and report the checks the plan gates on:
# page count, page of the References heading, per-section word counts,
# embedded fonts, and an anonymity grep over source and PDF text.
# Exits non-zero on compile error, unresolved-label warnings, missing
# TeX Gyre Termes, or any anonymity hit.
set -u
cd "$(dirname "$0")"

SRC=formalise2027.typ
PDF=formalise2027.pdf
LOG=.check-compile.log
# Also catches the author's Windows username and local absolute paths,
# which leak through trace/artifact paths in exported data.
ANON_TERMS='mcdonnell|ciaran?\b|\bucd\b|dublin|21320201|csgitlab|acknowledg|[A-Za-z]:[\\/]+Users[\\/]|/home/[a-z]'
fail=0

typst compile "$SRC" "$PDF" >"$LOG" 2>&1
rc=$?
if [ $rc -ne 0 ]; then
  echo "compile: FAILED"; cat "$LOG"; exit 1
fi
if grep -Eiq 'unknown label|unknown variable|label does not exist' "$LOG"; then
  echo "compile: WARNINGS (unresolved references)"; grep -Ei 'unknown|does not exist' "$LOG"; fail=1
else
  echo "compile: ok"
fi

uv run --quiet --with pypdf python - "$PDF" <<'PY'
import sys, re, pypdf
r = pypdf.PdfReader(sys.argv[1])
texts = [p.extract_text() or "" for p in r.pages]
print(f"pages: {len(r.pages)}")
# Case-insensitive: the IEEE template may set the heading in small caps or upper case.
ref = next((i + 1 for i, t in enumerate(texts) if re.search(r"^\s*References\s*$", t, re.M | re.I)), None)
print(f"references_page: {ref}")
fonts = set()
for p in r.pages:
    for f in (p.get("/Resources") or {}).get("/Font", {}).values():
        fonts.add(str(f.get_object().get("/BaseFont", "")).split("+")[-1])
print("fonts: " + ", ".join(sorted(fonts)))
if not any("TeXGyreTermes" in f for f in fonts):
    print("fonts: MISSING TeXGyreTermes"); sys.exit(2)
pat = re.compile(r"mcdonnell|ciaran?\b|\bucd\b|dublin|21320201|csgitlab|acknowledg|[A-Za-z]:[\\/]+Users[\\/]|/home/[a-z]", re.I)
hits = [(i + 1, m.group(0)) for i, t in enumerate(texts) for m in pat.finditer(t)]
meta = r.metadata or {}
if meta.get("/Author"):
    hits.append(("metadata", f"Author={meta.get('/Author')}"))
if hits:
    print("anonymity(pdf): HITS " + ", ".join(f"p{p}:{w}" for p, w in hits)); sys.exit(3)
print("anonymity(pdf): clean")
PY
rc=$?
[ $rc -ne 0 ] && fail=1

echo "words (incl. markup):"
for f in sections/*.typ; do printf "  %-32s %5d\n" "$f" "$(wc -w <"$f")"; done

# Paper source plus everything shipped in the anonymised artifact.
src_hits=$(grep -rEil "$ANON_TERMS" --include='*.typ' --include='*.bib' \
  --include='*.csv' --include='*.json' --include='*.py' --include='*.md' \
  . 2>/dev/null || true)
if [ -n "$src_hits" ]; then
  echo "anonymity(src): HITS in $src_hits"; grep -rEin "$ANON_TERMS" $src_hits | head; fail=1
else
  echo "anonymity(src): clean"
fi

exit $fail
