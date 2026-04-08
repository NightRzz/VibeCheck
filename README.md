# VibeCheck

VibeCheck is a small real-time sentiment pipeline. A FastAPI producer accepts raw text, Kafka carries the events, a worker scores them with TextBlob and writes the results to PostgreSQL, and a dashboard API streams live analytics to the browser over WebSockets.

The stack is intentionally simple:

- Apache Kafka 4.1 in KRaft mode
- PostgreSQL 18
- FastAPI for the ingest and dashboard services
- SQLAlchemy 2 async with `asyncpg`
- TextBlob for sentiment scoring
- Next.js and React for the frontend dashboard

## Project layout

`producer/main.py` exposes `POST /ingest` and publishes messages to the `raw-vibe-data` topic.  
`processor/worker.py` consumes Kafka messages, computes sentiment, and stores rows in `sentiments`.  
`api/main.py` serves `GET /analytics`, `GET /v1/tracked`, and WebSocket endpoints.  
`frontend/` contains the Next.js dashboard UI.  
`docker-compose.yml` starts PostgreSQL, Kafka, and the frontend for local development.

## Requirements

Use Python 3.11+ and Docker. On Windows that usually means Docker Desktop; on Linux any working Docker daemon is fine.

Install the Python dependencies with:

```bash
python -m pip install -r requirements.txt
```

## Running locally

The easiest way to run the whole stack is using Docker Compose:

```bash
docker compose up -d --build
```

This starts PostgreSQL, Kafka, the API (`:8000`), the producer (`:8001`), background workers, and the Next.js frontend (`:3000`).

Open `http://localhost:3000` to view the dashboard.

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

As new messages are processed, the dashboard updates the live feed, gauge, total count, average score, and range.

## Running components manually

If you want to develop without running everything in Docker, start the infrastructure first:

```bash
docker compose up -d postgres kafka
```

Then run these in separate terminals:

```bash
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
python -m uvicorn producer.main:app --host 0.0.0.0 --port 8001 --reload
python processor/worker.py
python youtube_ingestor/worker.py
```

For the frontend, run:

```bash
cd frontend
npm install
npm run dev
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
