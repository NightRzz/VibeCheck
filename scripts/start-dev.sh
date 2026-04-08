#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

INSTALL_DEPS=false
SKIP_DOCKER=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --install-deps)
      INSTALL_DEPS=true
      ;;
    --skip-docker)
      SKIP_DOCKER=true
      ;;
    *)
      echo "Unknown option: $1" >&2
      exit 1
      ;;
  esac
  shift
done

resolve_python() {
  if [[ -x "$REPO_ROOT/.venv/bin/python" ]]; then
    echo "$REPO_ROOT/.venv/bin/python"
    return
  fi

  if [[ -x "$REPO_ROOT/venv/bin/python" ]]; then
    echo "$REPO_ROOT/venv/bin/python"
    return
  fi

  if command -v python3 >/dev/null 2>&1; then
    command -v python3
    return
  fi

  command -v python
}

PYTHON_BIN="$(resolve_python)"
RUN_DIR="$REPO_ROOT/.run"
mkdir -p "$RUN_DIR"

if [[ "$INSTALL_DEPS" == true ]]; then
  "$PYTHON_BIN" -m pip install -r requirements.txt
fi

if [[ "$SKIP_DOCKER" == false ]]; then
  docker compose up -d postgres kafka
fi

start_process() {
  local name="$1"
  local command="$2"
  local log_file="$RUN_DIR/$name.log"
  local pid_file="$RUN_DIR/$name.pid"

  nohup bash -lc "$command" >"$log_file" 2>&1 &
  echo $! >"$pid_file"
}

start_process "api" "\"$PYTHON_BIN\" -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload"
start_process "producer" "\"$PYTHON_BIN\" -m uvicorn producer.main:app --host 0.0.0.0 --port 8001 --reload"
start_process "worker" "\"$PYTHON_BIN\" processor/worker.py"
start_process "youtube-ingestor" "\"$PYTHON_BIN\" -m youtube_ingestor.worker"

cat <<EOF
API dashboard: http://localhost:8000
Producer ingest: http://localhost:8001/ingest
Background logs: $RUN_DIR
EOF
