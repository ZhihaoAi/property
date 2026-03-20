#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PORT="${PORT:-4173}"
HOST="${HOST:-127.0.0.1}"
TAB="${1:-s10}"
AUTO_OPEN="${AUTO_OPEN:-1}"
PID_FILE="$ROOT_DIR/artifacts/dashboard_vite_server.pid"
LOG_FILE="$ROOT_DIR/artifacts/dashboard_vite_server.log"
URL="http://${HOST}:${PORT}/?tab=${TAB}"

usage() {
  cat <<EOF
Usage: ./restart_dashboard_server.sh [tab]

Examples:
  ./restart_dashboard_server.sh
  ./restart_dashboard_server.sh s12
  PORT=4174 ./restart_dashboard_server.sh s10
  AUTO_OPEN=0 ./restart_dashboard_server.sh s10
EOF
}

get_pid_command() {
  local pid="$1"
  ps -p "$pid" -o command= 2>/dev/null | sed 's/^ *//'
}

get_pid_cwd() {
  local pid="$1"
  if ! command -v lsof >/dev/null 2>&1; then
    return 0
  fi
  lsof -a -p "$pid" -d cwd -Fn 2>/dev/null | sed -n 's/^n//p' | head -n 1
}

is_our_server_pid() {
  local pid="$1"
  local cmd cwd

  if ! kill -0 "$pid" >/dev/null 2>&1; then
    return 1
  fi

  cmd="$(get_pid_command "$pid")"
  cwd="$(get_pid_cwd "$pid")"

  [[ "$cmd" == *"vite --host ${HOST} --port ${PORT} --strictPort"* ]] && [[ -n "$cwd" ]] && [[ "$cwd" == "$ROOT_DIR" ]]
}

stop_pid_if_running() {
  local pid="$1"
  if kill -0 "$pid" >/dev/null 2>&1; then
    kill "$pid" >/dev/null 2>&1 || true
    sleep 1
    if kill -0 "$pid" >/dev/null 2>&1; then
      kill -9 "$pid" >/dev/null 2>&1 || true
    fi
  fi
}

cleanup_pid_file() {
  if [[ ! -f "$PID_FILE" ]]; then
    return 0
  fi

  local pid
  pid="$(cat "$PID_FILE" 2>/dev/null || true)"
  if [[ -z "$pid" ]]; then
    rm -f "$PID_FILE"
    return 0
  fi

  if ! kill -0 "$pid" >/dev/null 2>&1; then
    rm -f "$PID_FILE"
    return 0
  fi

  if ! is_our_server_pid "$pid"; then
    echo "PID file points to an unrelated process. Removing stale pid file."
    rm -f "$PID_FILE"
  fi
}

stop_existing_server() {
  cleanup_pid_file

  if [[ ! -f "$PID_FILE" ]]; then
    return 0
  fi

  local pid
  pid="$(cat "$PID_FILE" 2>/dev/null || true)"
  if [[ -n "$pid" ]] && is_our_server_pid "$pid"; then
    echo "Stopping existing dashboard server PID ${pid}..."
    stop_pid_if_running "$pid"
  fi

  rm -f "$PID_FILE"
}

ensure_port_available() {
  if ! command -v lsof >/dev/null 2>&1; then
    return 0
  fi

  local pids
  pids="$(lsof -tiTCP:${PORT} -sTCP:LISTEN 2>/dev/null || true)"
  if [[ -z "$pids" ]]; then
    return 0
  fi

  while IFS= read -r pid; do
    [[ -n "$pid" ]] || continue

    if is_our_server_pid "$pid"; then
      echo "Stopping dashboard server PID ${pid} still bound to port ${PORT}..."
      stop_pid_if_running "$pid"
      continue
    fi

    echo "Port ${PORT} is occupied by another service; refusing to kill it." >&2
    echo "PID: ${pid}" >&2
    echo "Command: $(get_pid_command "$pid")" >&2
    echo "CWD: $(get_pid_cwd "$pid")" >&2
    echo "Use another port, for example: PORT=4174 ./restart_dashboard_server.sh ${TAB}" >&2
    exit 1
  done <<< "$pids"
}

wait_for_server() {
  local retries=80
  local attempt

  for ((attempt=1; attempt<=retries; attempt++)); do
    if command -v lsof >/dev/null 2>&1; then
      if lsof -iTCP:${PORT} -sTCP:LISTEN >/dev/null 2>&1; then
        return 0
      fi
    elif kill -0 "$SERVER_PID" >/dev/null 2>&1; then
      return 0
    fi
    sleep 0.25
  done

  return 1
}

start_server() {
  (
    cd "$ROOT_DIR"
    nohup ./node_modules/.bin/vite --host "$HOST" --port "$PORT" --strictPort >"$LOG_FILE" 2>&1 &
    echo $! >"$PID_FILE"
  )
}

open_page() {
  if [[ "$AUTO_OPEN" != "1" ]]; then
    return 0
  fi

  if command -v open >/dev/null 2>&1; then
    open "$URL" >/dev/null 2>&1 || true
    return 0
  fi

  if command -v xdg-open >/dev/null 2>&1; then
    xdg-open "$URL" >/dev/null 2>&1 || true
  fi
}

if [[ "${TAB}" == "-h" || "${TAB}" == "--help" ]]; then
  usage
  exit 0
fi

mkdir -p "$ROOT_DIR/artifacts"

echo "Stopping existing dashboard server..."
stop_existing_server

echo "Checking port ${PORT}..."
ensure_port_available

echo "Rebuilding dashboard data..."
(
  cd "$ROOT_DIR"
  python3 build_dashboard_data.py
)

echo "Starting Vite on ${HOST}:${PORT}..."
start_server

SERVER_PID="$(cat "$PID_FILE")"
if ! wait_for_server; then
  echo "Server failed to start. Check log: $LOG_FILE" >&2
  exit 1
fi

if ! is_our_server_pid "$SERVER_PID"; then
  echo "Started process does not match expected dashboard server signature. Check log: $LOG_FILE" >&2
  exit 1
fi

open_page

echo "Dashboard server is running."
echo "PID: $SERVER_PID"
echo "Log: $LOG_FILE"
echo "URL: $URL"
