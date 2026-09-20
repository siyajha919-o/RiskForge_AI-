#!/usr/bin/env bash
#
# RiskForge AI — start the whole system with one command.
#
#   ./start.sh              normal start (trains once if no models exist yet)
#   ./start.sh --retrain    force a full pipeline run before serving
#   ./start.sh --api-only   engine + API, no frontend
#
# Brings up, in order:
#   1. the Python risk engine (only if outputs/ is empty, or --retrain)
#   2. the FastAPI service on :8000
#   3. the Java API gateway on :8080
#   4. the Vite frontend on :5173
#
# The frontend talks only to the gateway, which serves the platform's own
# resources under /api/v1/platform and relays every other /api/v1 route to the
# FastAPI service. Skipping step 3 leaves the dashboard with nothing to call.
#
# Ctrl-C stops everything it started.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENGINE="$ROOT/RiskEngine"
FRONTEND="$ROOT/frontend"
BACKEND="$ROOT/cyber-risk-platform/backend"
JAR="$BACKEND/build/libs/cyber-risk-platform-0.1.0.jar"
RUN="$ROOT/.run"

API_PORT=8000
GATEWAY_PORT=8080
WEB_PORT=5173

# The Gradle build pins a Java 17 toolchain and macOS ships no JDK 17.
# ./run.sh setup installs one here.
JDK17="$HOME/.local/tools/jdk-17.0.20.1+1/Contents/Home"
[ -d "$JDK17" ] && export JAVA_HOME="$JDK17" && export PATH="$JAVA_HOME/bin:$PATH"

RETRAIN=0
API_ONLY=0
for arg in "$@"; do
  case "$arg" in
    --retrain)  RETRAIN=1 ;;
    --api-only) API_ONLY=1 ;;
    -h|--help)  sed -n '2,14p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "Unknown option: $arg (try --help)" >&2; exit 2 ;;
  esac
done

# ---------------------------------------------------------------- utilities
bold() { printf '\033[1m%s\033[0m\n' "$1"; }
dim()  { printf '\033[2m%s\033[0m\n' "$1"; }
die()  { printf '\033[31mERROR\033[0m %s\n' "$1" >&2; exit 1; }

# -sTCP:LISTEN matters: a bare `lsof -ti tcp:PORT` also matches spent client
# sockets in CLOSED/TIME_WAIT (an editor that once previewed the page leaves
# them behind), which made the script skip starting a server that wasn't there.
port_busy() { lsof -ti tcp:"$1" -sTCP:LISTEN >/dev/null 2>&1; }

# Wait for a URL to answer, or give up. Beats a fixed sleep: a cold TensorFlow
# import can take 20s on first run and under a second afterwards.
wait_for() {
  local url="$1" name="$2" tries="${3:-60}"
  for _ in $(seq "$tries"); do
    if curl -fsS -o /dev/null --max-time 2 "$url" 2>/dev/null; then return 0; fi
    sleep 1
  done
  die "$name did not come up at $url. Check the log above."
}

PIDS=()
cleanup() {
  echo
  dim "Shutting down…"
  for pid in "${PIDS[@]:-}"; do
    [ -n "$pid" ] && kill "$pid" 2>/dev/null || true
  done
  wait 2>/dev/null || true
  exit 0
}
trap cleanup INT TERM

# ------------------------------------------------------------ python venv
cd "$ENGINE"

VENV=""
for candidate in .venv venv; do
  [ -d "$candidate" ] && { VENV="$candidate"; break; }
done
if [ -z "$VENV" ]; then
  bold "Creating virtualenv (.venv)…"
  python3 -m venv .venv
  VENV=".venv"
  # shellcheck disable=SC1091
  source "$VENV/bin/activate"
  pip install --quiet --upgrade pip
  bold "Installing Python dependencies… (first run, this takes a few minutes)"
  pip install --quiet -r requirements.txt
else
  # shellcheck disable=SC1091
  source "$VENV/bin/activate"
fi

python -c 'import fastapi, uvicorn' 2>/dev/null || {
  bold "Installing Python dependencies…"
  pip install --quiet -r requirements.txt
}

[ -f .env ] || dim "No RiskEngine/.env — the API will generate a throwaway JWT secret."

# --------------------------------------------------------------- pipeline
# graph_data.json is the file every dashboard route reads; if it is missing the
# UI has nothing to draw, so treat it as the marker for "has this ever run".
if [ "$RETRAIN" -eq 1 ] || [ ! -f outputs/graph_data.json ]; then
  if [ "$RETRAIN" -eq 1 ]; then
    bold "Running the risk engine (full retrain)…"
    python main.py --mode full
  else
    bold "No pipeline output yet — running the risk engine once…"
    dim "This trains the models and runs FAIR + the optimiser. Several minutes."
    python main.py --mode full
  fi
else
  dim "Using existing pipeline output in RiskEngine/outputs (--retrain to redo)."
fi

# -------------------------------------------------------------------- API
if port_busy "$API_PORT"; then
  dim "Port $API_PORT already in use — reusing whatever is serving there."
else
  bold "Starting API on :${API_PORT}…"
  uvicorn api.main:app --port "$API_PORT" --log-level warning &
  PIDS+=($!)
fi
wait_for "http://localhost:$API_PORT/health" "API"

# ---------------------------------------------------------------- gateway
# Shared with run.sh so a token minted by one launcher survives the other.
mkdir -p "$RUN"
if [ ! -f "$RUN/jwt_secret" ]; then
  openssl rand -base64 64 | tr -d '\n' > "$RUN/jwt_secret"
  chmod 600 "$RUN/jwt_secret"
fi
export JWT_SECRET="$(cat "$RUN/jwt_secret")"
export ADMIN_BOOTSTRAP_EMAIL="${ADMIN_BOOTSTRAP_EMAIL:-admin@riskforge.io}"
export ADMIN_BOOTSTRAP_PASSWORD="${ADMIN_BOOTSTRAP_PASSWORD:-changeme-at-least-12-chars}"
export RISK_ENGINE_URL="${RISK_ENGINE_URL:-http://localhost:$API_PORT}"
export RISK_ENGINE_USERNAME="${RISK_ENGINE_USERNAME:-$ADMIN_BOOTSTRAP_EMAIL}"
export RISK_ENGINE_PASSWORD="${RISK_ENGINE_PASSWORD:-$ADMIN_BOOTSTRAP_PASSWORD}"

if port_busy "$GATEWAY_PORT"; then
  dim "Port $GATEWAY_PORT already in use — reusing whatever is serving there."
elif [ ! -f "$JAR" ]; then
  die "Gateway jar missing. Build it with: ./run.sh build"
else
  bold "Starting API gateway on :${GATEWAY_PORT}…"
  java -jar "$JAR" >"$RUN/backend.log" 2>&1 &
  PIDS+=($!)
fi
# The JVM needs a few seconds to open the port, so allow more tries than the API.
wait_for "http://localhost:$GATEWAY_PORT/actuator/health" "API gateway" 60

# --------------------------------------------------------------- frontend
if [ "$API_ONLY" -eq 0 ]; then
  cd "$FRONTEND"
  [ -d node_modules ] || { bold "Installing frontend dependencies…"; npm install --silent; }

  if port_busy "$WEB_PORT"; then
    dim "Port $WEB_PORT already in use — reusing whatever is serving there."
  else
    bold "Starting frontend on :${WEB_PORT}…"
    npm run dev -- --port "$WEB_PORT" >/dev/null 2>&1 &
    PIDS+=($!)
  fi
  wait_for "http://localhost:$WEB_PORT/" "Frontend" 45
fi

# ----------------------------------------------------------------- ready
echo
bold "RiskForge AI is up."
echo
if [ "$API_ONLY" -eq 0 ]; then
  echo "  Dashboard   http://localhost:$WEB_PORT"
fi
echo "  Gateway     http://localhost:$GATEWAY_PORT/actuator/health"
echo "  API docs    http://localhost:$API_PORT/docs"
echo
if [ -f "$ENGINE/.env" ]; then
  # Read straight from .env so this never drifts from the real account.
  EMAIL=$(grep -E '^ADMIN_BOOTSTRAP_EMAIL=' "$ENGINE/.env" | cut -d= -f2-)
  PASS=$(grep -E '^ADMIN_BOOTSTRAP_PASSWORD=' "$ENGINE/.env" | cut -d= -f2-)
  echo "  Sign in     ${EMAIL:-<see RiskEngine/.env>} / ${PASS:-<see RiskEngine/.env>}"
  echo
fi
dim "Ctrl-C to stop."

wait
