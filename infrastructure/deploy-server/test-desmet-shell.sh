#!/usr/bin/env bash
# Allow/deny checks for desmet-shell with stubbed git and docker.
#
# Needs root (desmet-shell's base directory is fixed at /opt/desmet), so
# run it in a throwaway container, e.g. from the repo root:
#
#   MSYS_NO_PATHCONV=1 docker run --rm -u root \
#     -v "$PWD/infrastructure/deploy-server:/shell:ro" \
#     desmet-eval-base:1.0 bash /shell/test-desmet-shell.sh
#
# Set PYTHON3=/path/to/python to run the compose policy under a Python
# with PyYAML (the stock base image has none, which exercises the
# no-yaml fallback).
set -uo pipefail

SHELL_UNDER_TEST="${SHELL_UNDER_TEST:-/shell/desmet-shell}"
BASE=/opt/desmet
STUB=$(mktemp -d)
fails=0

# docker stub: `compose ... config` prints the project's config.json (the
# fixture standing in for `docker compose config --format json`); every
# other call just echoes its argv.  Without --no-env-resolution config
# fails, as env_file would be resolved away (STUB_ANY_CONFIG=1 skips this,
# to run the checks against an older desmet-shell).
cat > "$STUB/docker" <<'EOF'
#!/usr/bin/env bash
if [ "$1" = compose ]; then
  dir=""; prev=""
  for a in "$@"; do
    [ "$prev" = --project-directory ] && dir="$a"
    prev="$a"
  done
  for a in "$@"; do
    if [ "$a" = config ]; then
      case " $* " in
        *" --no-env-resolution "*) ;;
        *) [ -n "${STUB_ANY_CONFIG:-}" ] || exit 1 ;;
      esac
      cat "$dir/config.json"; exit
    fi
  done
fi
echo "docker $*"
EOF
printf '#!/usr/bin/env bash\necho "git $*"\n' > "$STUB/git"
printf '#!/usr/bin/env bash\necho "curl $*"\n' > "$STUB/curl"
if [ -n "${PYTHON3:-}" ]; then
  printf '#!/usr/bin/env bash\nexec %s "$@"\n' "$PYTHON3" > "$STUB/python3"
fi
chmod +x "$STUB"/*
export PATH="$STUB:$PATH"

# project <name> <config-json> [file=content ...]: a deploy checkout
project() {
  local dir="$BASE/p/US-001/$1"; shift
  mkdir -p "$dir"
  printf '%s' "$1" > "$dir/config.json"; shift
  local kv
  for kv in "$@"; do printf '%s\n' "${kv#*=}" > "$dir/${kv%%=*}"; done
  echo "$dir"
}

expect() {  # expect allow|deny <label> <command>
  local want="$1" label="$2" out rc
  out=$(bash "$SHELL_UNDER_TEST" -c "$3" 2>&1); rc=$?
  if { [ "$want" = allow ] && [ $rc -eq 0 ]; } || { [ "$want" = deny ] && [ $rc -eq 126 ]; }; then
    echo "ok   $want: $label${VERBOSE:+ -- $out}"
  else
    echo "FAIL $want: $label (exit $rc): $out"; fails=$((fails + 1))
  fi
}

mkdir -p "$BASE" /home/outside
up() { echo "cd $1 && docker compose up -d --build --remove-orphans"; }
svc() { echo "{\"services\": {\"app\": $1}}"; }

# ── teardown: docker compose -p <project> down ─────────────────────────
expect allow "teardown of a desmet project" "cd $BASE && docker compose -p desmet-crewai down"
expect allow "teardown, underscore platform" "cd $BASE && docker compose -p desmet-agent_framework down"
expect deny "teardown of a non-desmet project" "cd $BASE && docker compose -p langfuse down"
expect deny "-p with another subcommand" "cd $BASE && docker compose -p desmet-crewai up -d"
expect deny "-p down with extra args" "cd $BASE && docker compose -p desmet-crewai down -v"
expect deny "teardown outside base" "docker compose -p desmet-crewai down"

# ── compose policy ─────────────────────────────────────────────────────
d=$(project ok "$(svc "{\"build\": {\"context\": \"$BASE/p/US-001/ok\", \"dockerfile\": \"Dockerfile\", \"additional_contexts\": {\"img\": \"docker-image://alpine\", \"lib\": \"$BASE/p/US-001/ok/lib\"}}, \"env_file\": [{\"path\": \"$BASE/p/US-001/ok/.env\"}]}")" \
  ".env=PORT=8002")
expect allow "build/env_file inside project" "$(up "$d")"

d=$(project ctx "$(svc "{\"build\": {\"context\": \"/home/outside\"}}")")
expect deny "build.context outside" "$(up "$d")"
d=$(project ctxurl "$(svc "{\"build\": {\"context\": \"git@github.com:x/y.git\"}}")")
expect deny "remote build.context" "$(up "$d")"
d=$(project df "$(svc "{\"build\": {\"context\": \"$BASE/p/US-001/df\", \"dockerfile\": \"../../../../home/outside/id_ed25519\"}}")")
expect deny "dockerfile outside" "$(up "$d")"
d=$(project addl "$(svc "{\"build\": {\"context\": \"$BASE/p/US-001/addl\", \"additional_contexts\": {\"k\": \"/home/outside\"}}}")")
expect deny "build.additional_contexts outside" "$(up "$d")"
d=$(project ssh "$(svc "{\"build\": {\"context\": \"$BASE/p/US-001/ssh\", \"ssh\": [\"default\"]}}")")
expect deny "build.ssh" "$(up "$d")"
d=$(project envf "$(svc "{\"env_file\": [{\"path\": \"/home/outside/.env\"}]}")")
expect deny "env_file outside" "$(up "$d")"
d=$(project envvar "$(svc "{\"env_file\": [{\"path\": \"\${HOME}/.env\"}]}")")
expect deny "env_file with unresolved variable" "$(up "$d")"
d=$(project bind "$(svc "{\"volumes\": [{\"type\": \"bind\", \"source\": \"/home/outside\"}]}")")
expect deny "bind mount outside (existing rule)" "$(up "$d")"
d=$(project dotenv "$(svc "{}")" ".env=COMPOSE_FILE=/home/outside/c.yaml")
expect deny ".env COMPOSE_FILE" "$(up "$d")"

d=$(project extout "$(svc "{}")" "compose.yaml=services: {app: {extends: {file: /home/outside/c.yaml, service: x}}}")
expect deny "extends outside" "$(up "$d")"
d=$(project incout "$(svc "{}")" "compose.yaml=include: [/home/outside/c.yaml]")
expect deny "include outside" "$(up "$d")"
if python3 -c "import yaml" 2>/dev/null; then
  d=$(project extin "$(svc "{}")" \
    "compose.yaml=services: {app: {extends: {file: base.yaml, service: x}}}" \
    "base.yaml=services: {x: {extends: {file: ../../../../home/outside/c.yaml, service: y}}}")
  expect deny "extends chain leaving the project" "$(up "$d")"
  d=$(project extok "$(svc "{}")" \
    "compose.yaml=include: [{path: inc.yaml}]" "inc.yaml=services: {x: {image: alpine}}")
  expect allow "include inside project" "$(up "$d")"
  d=$(project incenv "$(svc "{}")" "compose.yaml=include: [{path: inc.yaml, env_file: /home/outside/.env}]")
  expect deny "include env_file outside" "$(up "$d")"
else
  d=$(project extok "$(svc "{}")" "compose.yaml=include: [inc.yaml]")
  expect deny "include refused without python3-yaml" "$(up "$d")"
fi

echo
[ $fails -eq 0 ] && echo "all checks passed" || echo "$fails check(s) failed"
exit $fails
