#!/usr/bin/env bash
# Start, check, and stop one disposable Next Bracket instance.
# Kill only the PIDs this script records. Do not delete the evidence directory.
set -euo pipefail

SKILL_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SKILL_DIR/../../.." && pwd)"
RUN_DIR="${VERIFY_NEXTBRACKET_RUN_DIR:-$SKILL_DIR/run}"
EVIDENCE_DIR="$SKILL_DIR/evidence"

usage() {
  echo "usage: verify.sh {start|doctor|stop}" >&2
  exit 2
}

free_port() {
  python3 -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1",0)); print(s.getsockname()[1]); s.close()'
}

# Start a command in a new session so it keeps running after this script exits.
# Prints the detached pid. Env vars exported by the caller are inherited.
detach() {
  local cwd="$1" log="$2"
  shift 2
  python3 - "$cwd" "$log" "$@" <<'PY'
import os
import sys

cwd, log, *cmd = sys.argv[1:]
pid = os.fork()
if pid > 0:
    print(pid)
    raise SystemExit(0)
os.setsid()
os.chdir(cwd)
fd = os.open(log, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
os.dup2(fd, 1)
os.dup2(fd, 2)
os.execvp(cmd[0], cmd)
PY
}

load_state() {
  if [[ ! -f "$RUN_DIR/state.env" ]]; then
    echo "no instance recorded in $RUN_DIR" >&2
    exit 1
  fi
  # shellcheck disable=SC1091
  source "$RUN_DIR/state.env"
}

pid_alive() {
  kill -0 "$1" 2>/dev/null
}

kill_tree() {
  local pid="$1"
  local kid
  local kids
  kids="$(pgrep -P "$pid" || true)"
  for kid in $kids; do
    kill_tree "$kid"
  done
  kill "$pid" 2>/dev/null || true
}

wait_http() {
  local url="$1"
  local attempt
  for attempt in $(seq 1 90); do
    if curl -sf "$url" >/dev/null; then
      return 0
    fi
    sleep 1
  done
  echo "timed out waiting for $url" >&2
  return 1
}

known_score_ok() {
  local body
  body="$(curl -sf -X POST "$API_URL/score" \
    -H 'content-type: application/json' \
    -d '{"profile":{"age":27,"sex":"M"},"results":{"values":{"run_2mile":940,"push_up":45,"sit_up":50,"whtr":49}}}' || true)"
  python3 -c 'import json,sys
try:
    body=json.loads(sys.argv[1])
except Exception:
    raise SystemExit(1)
ok=body.get("total")==84.5 and body.get("category")=="satisfactory" and body.get("version")=="2026-03-01"
raise SystemExit(0 if ok else 1)' "$body"
}

cmd_start() {
  if [[ -f "$RUN_DIR/state.env" ]]; then
    # Source in a subshell. A live state file sets EVIDENCE_DIR to a run folder,
    # and sourcing it here would nest the next run's evidence path.
    if (
      # shellcheck disable=SC1091
      source "$RUN_DIR/state.env"
      pid_alive "${API_PID:-}" || pid_alive "${WEB_PID:-}"
    ); then
      # shellcheck disable=SC1091
      source "$RUN_DIR/state.env"
      echo "an instance is already recorded in $RUN_DIR (web $WEB_URL). Stop it, or set VERIFY_NEXTBRACKET_RUN_DIR for a second one." >&2
      exit 1
    fi
  fi

  mkdir -p "$RUN_DIR" "$EVIDENCE_DIR"
  : >"$RUN_DIR/api.log"
  : >"$RUN_DIR/web.log"
  local api_port web_port run_id
  api_port="$(free_port)"
  web_port="$(free_port)"
  run_id="$(date +%Y%m%dT%H%M%S)"

  local nvm_sh="${NVM_DIR:-$HOME/.nvm}/nvm.sh"
  if [[ -s "$nvm_sh" ]]; then
    # shellcheck disable=SC1090
    source "$nvm_sh"
    nvm use "$(tr -d '[:space:]' < "$ROOT/frontend/.nvmrc")"
  fi

  export NEXTBRACKET_CORS_ORIGINS="[\"http://127.0.0.1:${web_port}\"]"
  local api_pid
  api_pid="$(detach "$ROOT/backend" "$RUN_DIR/api.log" uv run uvicorn app.main:app --host 127.0.0.1 --port "$api_port")"
  unset NEXTBRACKET_CORS_ORIGINS

  export NEXT_PUBLIC_API_URL="http://127.0.0.1:${api_port}"
  local web_pid
  web_pid="$(detach "$ROOT/frontend" "$RUN_DIR/web.log" npm run dev -- --hostname 127.0.0.1 --port "$web_port")"
  unset NEXT_PUBLIC_API_URL

  cat >"$RUN_DIR/state.env" <<EOF
RUN_ID=$run_id
API_PID=$api_pid
WEB_PID=$web_pid
API_PORT=$api_port
WEB_PORT=$web_port
API_URL=http://127.0.0.1:$api_port
WEB_URL=http://127.0.0.1:$web_port
EVIDENCE_DIR=$EVIDENCE_DIR/$run_id
NODE_VERSION=$(node -v)
EOF

  # shellcheck disable=SC1091
  source "$RUN_DIR/state.env"
  mkdir -p "$EVIDENCE_DIR"

  if ! wait_http "$API_URL/health"; then
    echo "API failed to become ready. See $RUN_DIR/api.log" >&2
    cmd_stop || true
    exit 1
  fi
  if ! wait_http "$WEB_URL"; then
    echo "website failed to become ready. See $RUN_DIR/web.log" >&2
    cmd_stop || true
    exit 1
  fi
  known_score_ok
  cmd_doctor
}

cmd_doctor() {
  load_state
  local ok=0
  if ! pid_alive "$API_PID"; then
    echo "fail api pid $API_PID is not running" >&2
    ok=1
  fi
  if ! pid_alive "$WEB_PID"; then
    echo "fail web pid $WEB_PID is not running" >&2
    ok=1
  fi
  local health
  health="$(curl -sf "$API_URL/health" || true)"
  if [[ "$health" != *'"status":"ok"'* && "$health" != *'"status": "ok"'* ]]; then
    echo "fail health from $API_URL/health: ${health:-no response}" >&2
    ok=1
  fi
  if ! known_score_ok; then
    echo "fail known score (age 27 male, 15:40 run, 45 push-ups, 50 sit-ups, WHtR 0.49) was not 84.5 satisfactory on $API_URL" >&2
    ok=1
  fi
  local page
  page="$(curl -sf "$WEB_URL" || true)"
  if [[ "$page" != *"Next Bracket"* ]]; then
    echo "fail $WEB_URL did not serve the Next Bracket page" >&2
    ok=1
  fi
  local listen
  listen="$(lsof -nP -iTCP:"$API_PORT" -sTCP:LISTEN -t 2>/dev/null || true)"
  if [[ -n "$listen" && "$listen" != *"$API_PID"* ]]; then
    local child
    child="$(pgrep -P "$API_PID" || true)"
    if [[ -n "$child" && "$listen" != *"$child"* ]]; then
      echo "fail port $API_PORT is not owned by api pid $API_PID (listeners: $listen)" >&2
      ok=1
    fi
  fi
  if [[ "$ok" -ne 0 ]]; then
    exit 1
  fi
  echo "ok run $RUN_ID"
  echo "ok api $API_URL pid $API_PID"
  echo "ok web $WEB_URL pid $WEB_PID"
  echo "ok node $NODE_VERSION (frontend/.nvmrc wants $(tr -d '[:space:]' < "$ROOT/frontend/.nvmrc"))"
  echo "ok known score 84.5 satisfactory charts 2026-03-01"
  echo "ok evidence $EVIDENCE_DIR"
}

cmd_stop() {
  if [[ ! -f "$RUN_DIR/state.env" ]]; then
    echo "no instance recorded in $RUN_DIR"
    exit 0
  fi
  # shellcheck disable=SC1091
  source "$RUN_DIR/state.env"
  if [[ -n "${WEB_PID:-}" ]]; then
    kill_tree "$WEB_PID"
  fi
  if [[ -n "${API_PID:-}" ]]; then
    kill_tree "$API_PID"
  fi
  sleep 1
  if [[ -n "${WEB_PID:-}" ]] && pid_alive "$WEB_PID"; then
    kill -9 "$WEB_PID" 2>/dev/null || true
  fi
  if [[ -n "${API_PID:-}" ]] && pid_alive "$API_PID"; then
    kill -9 "$API_PID" 2>/dev/null || true
  fi
  rm -rf "$RUN_DIR"
  echo "stopped run ${RUN_ID:-unknown}. evidence kept under $SKILL_DIR/evidence"
}

case "${1:-}" in
  start) cmd_start ;;
  doctor) cmd_doctor ;;
  stop) cmd_stop ;;
  *) usage ;;
esac
