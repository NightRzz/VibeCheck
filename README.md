# VibeCheck

VibeCheck is a small real-time sentiment pipeline. A FastAPI producer accepts raw text, Kafka carries the events, a worker scores them with TextBlob and writes the results to PostgreSQL, and a dashboard API streams live analytics to the browser over WebSockets.

The stack is intentionally simple:

- Apache Kafka 4.1 in KRaft mode
- PostgreSQL 18
- FastAPI for the ingest and dashboard services
- SQLAlchemy 2 async with `asyncpg`
- TextBlob for sentiment scoring

## Project layout

`producer/main.py` exposes `POST /ingest` and publishes messages to the `raw-vibe-data` topic.  
`processor/worker.py` consumes Kafka messages, computes sentiment, and stores rows in `sentiments`.  
`api/main.py` serves `GET /analytics`, `GET /`, and `WebSocket /live-feed`.  
`api/index.html` is the dashboard UI.  
`docker-compose.yml` starts PostgreSQL and Kafka for local development.

## Requirements

Use Python 3.11+ and Docker. On Windows that usually means Docker Desktop; on Linux any working Docker daemon is fine.

Install the Python dependencies with:

```bash
python -m pip install -r requirements.txt
```

## Running locally

If you want the shortest path, use the helper scripts.

On Windows PowerShell:

```powershell
.\scripts\start-dev.ps1 -InstallDeps
```

On Linux or macOS shells:

```bash
./scripts/start-dev.sh --install-deps
```

Those scripts start PostgreSQL and Kafka with Docker Compose, then launch:

- the dashboard API on `http://localhost:8000`
- the producer API on `http://localhost:8001`
- the worker process that consumes Kafka and writes to Postgres

The PowerShell script opens separate windows. The shell script runs the services in the background and stores logs and PID files in `.run/`.

Open `http://localhost:8000` after the processes are up.

## Sending test traffic

You can post messages by hand:

```powershell
Invoke-RestMethod -Uri "http://localhost:8001/ingest" `
  -Method Post `
  -Headers @{"Content-Type"="application/json"} `
  -Body '{"source_id":"manual_test","text":"This pipeline feels great."}'
```

or:

```bash
curl -X POST http://localhost:8001/ingest \
  -H 'Content-Type: application/json' \
  -d '{"source_id":"manual_test","text":"This pipeline feels great."}'
```

If you want a stream of sample messages instead, use the helper scripts.

PowerShell:

```powershell
.\scripts\send-sample-vibes.ps1 -Count 20 -DelayMs 500
```

Shell:

```bash
./scripts/send-sample-vibes.sh --count 20 --delay-ms 500
```

As new messages are processed, the dashboard updates the live feed, gauge, total count, average score, and range.

## Running components manually

If you do not want to use the scripts, start infrastructure first:

```bash
docker compose up -d postgres kafka
```

Then run these in separate terminals:

```bash
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
python -m uvicorn producer.main:app --host 0.0.0.0 --port 8001 --reload
python processor/worker.py
```

## API summary

`POST /ingest` accepts:

```json
{
  "source_id": "user_123",
  "text": "This release is solid."
}
```

`GET /analytics` returns totals, average score, min and max score, plus the latest rows.  
`WebSocket /live-feed` emits newly processed sentiment rows as they arrive.

## Notes

This project uses TextBlob for a light sentiment baseline. It is easy to replace `analyze_sentiment()` in `processor/worker.py` with a transformer model later if you need better accuracy.
