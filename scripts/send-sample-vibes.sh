#!/usr/bin/env bash
set -euo pipefail

COUNT=12
DELAY_MS=750
URI="http://localhost:8001/ingest"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --count)
      COUNT="$2"
      shift
      ;;
    --delay-ms)
      DELAY_MS="$2"
      shift
      ;;
    --uri)
      URI="$2"
      shift
      ;;
    *)
      echo "Unknown option: $1" >&2
      exit 1
      ;;
  esac
  shift
done

samples=(
  "This launch feels smooth and reliable."
  "I love how responsive this pipeline is."
  "This is terrible and constantly broken."
  "The dashboard is useful but still a bit rough."
  "Absolutely fantastic experience so far."
  "I am frustrated by the delays today."
  "This feels stable, fast, and clean."
  "The service is failing and I do not trust it."
  "Pretty neutral update, nothing major changed."
  "This is the best result we have seen all week."
)

for ((i=1; i<=COUNT; i++)); do
  index=$((RANDOM % ${#samples[@]}))
  text="${samples[$index]}"
  payload=$(printf '{"source_id":"test_user_%d","text":"%s"}' "$i" "$text")

  response=$(
    curl -sS -X POST "$URI" \
      -H 'Content-Type: application/json' \
      -d "$payload"
  )

  echo "[$i/$COUNT] $response"

  if [[ "$i" -lt "$COUNT" ]]; then
    python_delay=$(python - <<PY
delay_ms = $DELAY_MS
print(delay_ms / 1000)
PY
)
    sleep "$python_delay"
  fi
done
