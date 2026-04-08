# VibeCheck

VibeCheck is a modern, real-time sentiment analysis pipeline built for live streaming platforms. It actively monitors YouTube Live chat streams, computes sentiment scores on incoming messages in real-time, and streams the analytics directly to a sleek Next.js dashboard via WebSockets.

Designed with a robust, event-driven architecture, VibeCheck is built to handle high-throughput chat streams efficiently and reliably.

## Features

- **Multi-Stream Tracking:** Simultaneously track and analyze multiple active YouTube Live streams.
- **Real-Time Sentiment Analysis:** Instantly scores incoming messages using Natural Language Processing (TextBlob).
- **Live Dashboard:** A responsive, modern React/Next.js dashboard that visualizes sentiment trends and streams live chat messages over WebSockets.
- **Robust Event Pipeline:** Utilizes Apache Kafka for reliable, decoupled message ingestion and processing.
- **Deduplication:** Ensures data integrity by strictly deduplicating messages at the database level.
- **Fully Dockerized:** Spin up the entire multi-container architecture with a single command.

## Architecture

VibeCheck is composed of several independent microservices:

1. **Frontend Dashboard (`frontend/`):** A Next.js application providing the user interface. It connects to the API via REST for statistics and WebSockets for the live feed.
2. **API Service (`api/main.py`):** A FastAPI application that serves global and video-specific analytics, manages tracked streams, and broadcasts new sentiment rows to connected WebSocket clients.
3. **YouTube Ingestor (`youtube_ingestor/worker.py`):** A background worker that continuously polls the YouTube API for new live chat comments across all tracked videos, publishing them to Kafka.
4. **Sentiment Processor (`processor/worker.py`):** The core Kafka consumer. It reads raw messages, computes the sentiment score using TextBlob, and persists the data into PostgreSQL.

### Tech Stack
- **Backend:** Python 3.11+, FastAPI, SQLAlchemy 2 (asyncpg)
- **Frontend:** TypeScript, React, Next.js, TailwindCSS
- **Message Broker:** Apache Kafka 4.1 (KRaft mode)
- **Database:** PostgreSQL 18
- **NLP:** TextBlob

## Getting Started

The easiest way to run the entire stack locally is using Docker Compose.

### Prerequisites
- Docker & Docker Compose
- A YouTube Data API Key

### Running with Docker

1. **Set up your YouTube API Key:**
   Create a `.env` file in the root directory (or export the variable in your shell) and add your key:
   ```env
   YOUTUBE_API_KEY=your_api_key_here
   ```

2. **Start the stack:**
   ```bash
   docker compose up -d --build
   ```
   This will spin up PostgreSQL, Kafka, the API (`:8000`), the background workers, and the Next.js Frontend (`:3000`).

3. **View the Dashboard:**
   Open [http://localhost:3000](http://localhost:3000) in your browser.

## Local Development Setup

If you prefer to run the components manually for active development, start the infrastructure first:

```bash
docker compose up -d postgres kafka
```

Install the backend Python dependencies:
```bash
python -m pip install -r requirements.txt
```

Run the backend components in separate terminals:
```bash
# Dashboard API
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload

# Sentiment Processor Worker
python processor/worker.py

# YouTube Ingestor Worker
python youtube_ingestor/worker.py
```

Run the frontend dashboard:
```bash
cd frontend
npm install
npm run dev
```

## API Summary

The backend exposes several key endpoints on port `8000`:

- `POST /v1/track`: Start tracking a new YouTube Live video.
- `DELETE /v1/track/{video_id}`: Stop tracking and delete data for a specific video.
- `GET /v1/tracked`: List all currently tracked videos and global metrics.
- `GET /analytics`: Get global sentiment totals and ranges.
- `GET /v1/analytics/{video_id}`: Get sentiment statistics for a specific video.
- `WebSocket /live-feed`: Global real-time stream of all processed messages.
- `WebSocket /live-feed/{video_id}`: Real-time stream of messages for a specific video.

## Notes & Future Improvements

- **NLP Model:** This project currently uses TextBlob to provide a lightweight sentiment baseline. It is intentionally decoupled so that the `analyze_sentiment()` function in `processor/worker.py` can be easily swapped out for a heavier transformer model (e.g., via Hugging Face) if better contextual accuracy is required.
