#!/usr/bin/env bash
# The whole product on this machine, without Docker: the control plane (the
# API, the site and the app) and one runner with the demo allowlist.
#
#   scripts/dev.sh                    SQLite in .teeter/, port 8000
#   PORT=8100 scripts/dev.sh
#   TEETER_DATABASE_URL=postgresql+psycopg://… scripts/dev.sh
#
# The first run makes .venv/ and installs the three packages into it, the
# engine first so pip never looks for it anywhere else. Ctrl-C stops both
# processes; the workspace, its campaigns and the tokens stay in .teeter/
# (or $TEETER_STATE_DIR).
set -euo pipefail
cd "$(dirname "$0")/.."

PORT=${PORT:-8000}
VENV=${VENV:-.venv}
API="http://127.0.0.1:$PORT"
STATE=${TEETER_STATE_DIR:-.teeter}
export TEETER_PUBLIC_URL="$API"

if [ ! -x "$VENV/bin/teeter-api" ] || [ ! -x "$VENV/bin/teeter" ]; then
  echo "· installing the engine, the API and the runner into $VENV"
  python3 -m venv "$VENV"
  "$VENV/bin/pip" install -q --upgrade pip
  "$VENV/bin/pip" install -q -e "harness[dev]"
  "$VENV/bin/pip" install -q -e "api[dev]"
  "$VENV/bin/pip" install -q -e "runner[dev]"
fi

"$VENV/bin/teeter-api" demo

# the runner first, so it can hand a job back while the API still answers
SERVER= RUNNER=
cleanup() {
  trap - EXIT INT TERM
  if [ -n "$RUNNER" ]; then kill "$RUNNER" 2>/dev/null || true; wait "$RUNNER" 2>/dev/null || true; fi
  if [ -n "$SERVER" ]; then kill "$SERVER" 2>/dev/null || true; wait "$SERVER" 2>/dev/null || true; fi
}
trap cleanup EXIT INT TERM

"$VENV/bin/teeter-api" serve --port "$PORT" &
SERVER=$!
for _ in $(seq 1 50); do
  if "$VENV/bin/python" -c "import urllib.request; urllib.request.urlopen('$API/v1/health', timeout=1)" 2>/dev/null; then
    break
  fi
  sleep 0.2
done

"$VENV/bin/teeter" runner start --api "$API" --token-file "$STATE/runner-token" \
  --config runner/demo-runner.yaml --name "$(hostname -s 2>/dev/null || echo local)-dev" &
RUNNER=$!

echo
echo "· the app is at $API/app/ — open the sign-in link above"
echo "· gate from another shell:  $VENV/bin/teeter gate --api $API --token-file $STATE/ci-token --program quadruped --checkpoint tall-v2"
wait
