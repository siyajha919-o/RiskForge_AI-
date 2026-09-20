#!/usr/bin/env bash
# RiskForge_AI — one-command launcher for the full stack.
#
#   ./run.sh setup     install Python + Node dependencies (first time only)
#   ./run.sh refresh   stop, clear caches, recompute, restart, verify  <- daily driver
#                      (--full also retrains the ML models)
#   ./run.sh status    what is up, when it last ran, whether inputs changed
#   ./run.sh pipeline  run the risk engine once (--mode full retrains the models)
#   ./run.sh build     compile the Java Spring Boot backend
#   ./run.sh start     start engine (:8000), Java backend (:8080), dashboard (:5173)
#   ./run.sh stop      stop all three
#   ./run.sh agent     report this machine's posture to the engine
#
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENGINE="$ROOT/RiskEngine"
FRONTEND="$ROOT/frontend"
PY="$ENGINE/.venv/bin/python"
BACKEND="$ROOT/cyber-risk-platform/backend"
RUN="$ROOT/.run"
mkdir -p "$RUN"

# The Gradle build pins a Java 17 toolchain, and no JDK 17 ships with macOS.
JDK17="$HOME/.local/tools/jdk-17.0.20.1+1/Contents/Home"
[ -d "$JDK17" ] && export JAVA_HOME="$JDK17" && export PATH="$JAVA_HOME/bin:$PATH"

# The Java backend refuses to start without a signing key. Persist one so tokens
# survive restarts instead of being invalidated on every boot.
if [ ! -f "$RUN/jwt_secret" ]; then
  openssl rand -base64 64 | tr -d '\n' > "$RUN/jwt_secret"
  chmod 600 "$RUN/jwt_secret"
fi
export JWT_SECRET="$(cat "$RUN/jwt_secret")"
export ADMIN_BOOTSTRAP_EMAIL="${ADMIN_BOOTSTRAP_EMAIL:-admin@riskforge.io}"
export ADMIN_BOOTSTRAP_PASSWORD="${ADMIN_BOOTSTRAP_PASSWORD:-changeme-at-least-12-chars}"
export RISK_ENGINE_URL="${RISK_ENGINE_URL:-http://localhost:8000}"
# The engine has no service-account concept, so the backend signs in as a user.
export RISK_ENGINE_USERNAME="${RISK_ENGINE_USERNAME:-$ADMIN_BOOTSTRAP_EMAIL}"
export RISK_ENGINE_PASSWORD="${RISK_ENGINE_PASSWORD:-$ADMIN_BOOTSTRAP_PASSWORD}"

# uv installs a pinned Python without needing Homebrew or sudo.
export PATH="$HOME/.local/bin:$PATH"

setup() {
  command -v uv >/dev/null || curl -LsSf https://astral.sh/uv/install.sh | sh
  # The pinned requirements (scipy>=1.14) need Python 3.10+; the system 3.9 fails.
  uv venv --python 3.12 "$ENGINE/.venv"
  uv pip install --python "$PY" -r "$ENGINE/requirements.txt"
  (cd "$FRONTEND" && npm install)
  # JDK 17 for the Gradle toolchain — user-local, no sudo.
  if [ ! -d "$JDK17" ]; then
    mkdir -p "$HOME/.local/tools"
    curl -sL "https://api.adoptium.net/v3/binary/latest/17/ga/mac/$(uname -m | sed 's/arm64/aarch64/')/jdk/hotspot/normal/eclipse" \
      | tar xz -C "$HOME/.local/tools"
    export JAVA_HOME="$JDK17"; export PATH="$JAVA_HOME/bin:$PATH"
  fi
  build
  echo "Setup complete. Next: ./run.sh pipeline && ./run.sh start"
}

spawn() {
  name=$1; dir=$2; shift 2
  ( cd "$dir" && exec perl -e 'setpgrp; exec @ARGV' "$@" \
      > "$RUN/$name.log" 2>&1 < /dev/null ) &
  echo $! > "$RUN/$name.pid"
}

pipeline() { (cd "$ENGINE" && "$PY" main.py "${@:---mode full}"); }

build() { (cd "$BACKEND" && ./gradlew build); }

JAR="$BACKEND/build/libs/cyber-risk-platform-0.1.0.jar"

# Gradle is the slowest step by far, so pay for it only when a source file is
# actually newer than the jar it produced.
build_if_stale() {
  if [ ! -f "$JAR" ] || [ -n "$(find "$BACKEND/src" -newer "$JAR" -print -quit 2>/dev/null)" ]; then
    echo "Java sources changed - rebuilding."
    build
  fi
}

# probe <label> <url> [tries]
# Polls rather than checking once: the JVM needs ~3.5s to open :8080, so a
# single immediate probe reports a healthy backend as down.
probe() {
  local tries="${3:-20}"
  for _ in $(seq "$tries"); do
    if curl -sf -m 3 "$2" >/dev/null 2>&1; then
      printf '  ok    %-14s %s\n' "$1" "$2"; return 0
    fi
    sleep 1
  done
  printf '  DOWN  %-14s %s\n' "$1" "$2"; return 1
}

verify() {
  echo "Verifying:"
  local bad=0 t="${QUICK:-20}"
  probe "risk engine"  http://127.0.0.1:8000/health           "$t" || bad=1
  probe "java backend" http://127.0.0.1:8080/actuator/health  "$t" || bad=1
  probe "dashboard"    http://127.0.0.1:5173/                 "$t" || bad=1
  [ "$bad" -eq 0 ] && echo "All services healthy." || echo "Some services are down - see $RUN/*.log"
  return 0
}

status() {
  QUICK=3 verify
  curl -sf -m 6 http://127.0.0.1:8000/health 2>/dev/null | "$PY" "$ROOT/.run/status.py" || true
}

# Stop, clear anything stale, recompute, restart, prove it came back.
refresh() {
  [ -x "$PY" ] || { echo "Run ./run.sh setup first."; exit 1; }
  local mode="incremental"
  [ "${1:-}" = "--full" ] && mode="full"

  echo "==> Stopping"
  stop
  sleep 2

  # Vite resolves deleted/renamed modules from this cache and serves code that
  # no longer exists in the source tree. Clearing it is the point of 'refresh'.
  echo "==> Clearing stale caches"
  rm -rf "$FRONTEND/node_modules/.vite"

  echo "==> Checking Java build"
  build_if_stale

  echo "==> Recomputing risk ($mode)"
  pipeline --mode "$mode"

  echo "==> Starting"
  start
  verify
}

start() {
  [ -x "$PY" ] || { echo "Run ./run.sh setup first."; exit 1; }
  # Starting over a live instance orphans it: the pid file is overwritten, the
  # old process keeps the port, and the new one silently lands somewhere else —
  # which looks exactly like a stale build. Clear whatever is already up first.
  if [ -f "$RUN/api.pid" ] || [ -f "$RUN/ui.pid" ] || [ -f "$RUN/backend.pid" ]; then
    echo "Services already started — restarting."
    stop
    sleep 2
  fi
  spawn api     "$ENGINE"  "$PY" -m uvicorn api.main:app --host 127.0.0.1 --port 8000
  if [ -f "$JAR" ]; then
    spawn backend "$BACKEND" java -jar "$JAR"
  else
    echo "Java backend not built — run ./run.sh build. Skipping :8080."
  fi
  spawn ui      "$FRONTEND" npm run dev
  # Wait for the API rather than guessing, so a failed boot is reported here.
  for _ in $(seq 30); do
    curl -sf -m 2 http://127.0.0.1:8000/health >/dev/null && break || sleep 1
  done
  echo "Risk engine   http://127.0.0.1:8000/docs"
  echo "Java backend  http://127.0.0.1:8080/actuator/health"
  echo "Dashboard     http://127.0.0.1:5173"
  echo "Logs          $RUN/{api,backend,ui}.log"
}

stop() {
  for p in api backend ui; do
    [ -f "$RUN/$p.pid" ] || continue
    pgid=$(cat "$RUN/$p.pid")
    # Negative PID targets the whole process group, so npm's vite child and the
    # JVM's helpers go with it instead of reparenting to init and lingering.
    kill -- "-$pgid" 2>/dev/null || true
    rm -f "$RUN/$p.pid"
  done
  echo "Stopped."
}

agent() { python3 "$ROOT/agent/riskforge_agent.py" --server http://127.0.0.1:8000 "$@"; }

case "${1:-}" in
  setup) setup ;;
  pipeline) shift; pipeline "$@" ;;
  refresh) shift; refresh "${1:-}" ;;
  status) status ;;
  build) build ;;
  start) start ;;
  stop) stop ;;
  restart) stop; start ;;
  agent) shift; agent "$@" ;;
  *) sed -n '2,12p' "$0"; exit 1 ;;
esac
