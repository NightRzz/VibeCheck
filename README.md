# VibeCheck

VibeCheck is an event-driven, production-grade sentiment analysis streaming and MLOps pipeline built for high-velocity live streaming platforms (such as YouTube Live and Twitch). 

It continuously ingests live chat streams via Apache Kafka, computes sentiment scores using a CPU-optimized **Contextual Deep Learning Transformer (Twitter-RoBERTa-base ONNX INT8)** with in-memory **LRU prediction caching**, and streams real-time analytics to a Next.js dashboard via WebSockets. It includes full **MLflow** experiment tracking and continuous **Data & Prediction Drift monitoring** powered by **Evidently AI**.

---

## Key Features

- **Contextual Transformer (Deep Learning on CPU):** Powered by Cardiff NLP's **`cardiffnlp/twitter-roberta-base-sentiment-latest`** quantized to **INT8** and executed via **ONNX Runtime**. Deeply understands semantic sentence context, negations (e.g. *"not bad"*, *"not terrible"* correctly scored positive), sarcasm, and live-chat syntax.
- **Micro-Latency CPU Serving:** Runs completely on standard CPU instances without expensive GPU infrastructure:
  - **In-memory LRU Cache:** Caches high-frequency live chat chatter (`W`, `L`, `KEKW`, emojis, slang), yielding sub-millisecond ($0.001\text{ ms}$) responses for recurring patterns.
  - **ONNX Runtime Graph Optimizations:** Quantized forward-pass execution in under $8\text{–}15\text{ ms}$ on CPU.
- **Academic Benchmark Provenance:** Evaluated on the Cardiff NLP **`cardiffnlp/tweet_eval` (SemEval)** benchmark (58,000+ real-world social media comments from Hugging Face), achieving **72–74% Macro F1** compared to legacy 56% baseline.
- **MLflow Experiment Tracking:** Automated parameter logging (architecture, quantization, sequence length, runtime), metric tracking (Accuracy, Macro F1, Weighted F1, latency percentiles), and model configuration versioning.
- **Continuous Drift & Quality Monitoring:** Integrated with **Evidently AI** to monitor:
  - **Data Drift:** Message length, token count, and uppercase spam ratio.
  - **Prediction Drift:** Kolmogorov-Smirnov / Wasserstein distance distribution shifts on sentiment scores.
  - Interactive HTML dashboard served live at `GET /v1/ml/drift-report` and JSON metrics at `GET /v1/ml/stats`.
- **Event-Driven Streaming:** Apache Kafka (KRaft mode) for decoupled, backpressure-resilient message ingestion and deduplication.
- **Live WebSocket Dashboard:** Modern Next.js (TailwindCSS) real-time visualizer with sub-second feedback loops.

---

## Architecture

```
[ YouTube Live API ]
        │ (Poll comments)
        ▼
[ YouTube Ingestor ] ──────► [ Apache Kafka (KRaft) ]
                             (Topic: raw-vibe-stream)
                                       │
                                       ▼
                             [ Sentiment Processor ]
                                       │
                ┌──────────────────────┴──────────────────────┐
                ▼                                             ▼
        [ LRU Prediction Cache ]                    [ Contextual Transformer ]
        (Repeated chat spam/emojis)                 (Twitter-RoBERTa ONNX INT8)
                │                                             │
                └──────────────────────┬──────────────────────┘
                                       ▼ (Sub-10ms Contextual Score)
                             [ PostgreSQL (asyncpg) ]
                                       │
        ┌──────────────────────────────┴──────────────────────────────┐
        ▼                                                             ▼
[ FastAPI Backend ]                                          [ Evidently AI Monitoring ]
  ├─ REST API & WebSockets                                     ├─ Data & Prediction Drift
  ├─ GET /v1/ml/stats                                          └─ GET /v1/ml/drift-report
  └─ WebSocket /live-feed
        │
        ▼
[ Next.js React Dashboard ]
```

### Microservices Breakdown
1. **Frontend Dashboard (`frontend/`):** Next.js dashboard providing stream controls, sentiment distribution charts, and real-time live feeds over WebSockets.
2. **API Service (`api/main.py`):** FastAPI service exposing analytical endpoints, tracked video management, WebSocket broadcasting, and MLOps health metrics (`/v1/ml/stats`, `/v1/ml/drift-report`).
3. **YouTube Ingestor (`youtube_ingestor/worker.py`):** Background worker streaming live chat comments into Kafka.
4. **Sentiment Processor (`processor/worker.py`):** Kafka consumer running `SentimentEngine` for contextual CPU scoring and transactional PostgreSQL persistence.
5. **MLOps & Monitoring (`ml/`):** Model training, MLflow tracking (`ml/train.py`), CPU latency benchmarking (`ml/evaluate.py`), and Evidently AI drift reports (`ml/monitoring.py`).

### Tech Stack
- **Languages & Frameworks:** Python 3.10+, FastAPI, Next.js, React, TailwindCSS, TypeScript
- **Deep Learning & MLOps:** ONNX Runtime (INT8 Quantization), Hugging Face Tokenizers (Rust BPE), MLflow, Evidently AI
- **Messaging & Database:** Apache Kafka 4.1 (KRaft), PostgreSQL, SQLAlchemy 2 (asyncpg)
- **Infrastructure:** Docker, Docker Compose

---

## MLOps & Machine Learning Workflows

### 1. Train Models & Track Experiments (MLflow)
Train candidate models (Logistic Regression vs. XGBoost), log metrics to MLflow, and export the best model artifact:

```bash
python -m ml.train
```

View the MLflow tracking dashboard:
```bash
mlflow ui --port 5000
```

### 2. Profile & Benchmark CPU Inference Latency
Run the standalone CPU latency and throughput benchmark suite:

```bash
python -m ml.evaluate
```

**Benchmark Results (WSL2 CPU):**
| Metric | Result |
| :--- | :--- |
| **Throughput (Single-item)** | $\sim 390{,}000\text{ items/sec}$ |
| **Throughput (Batch Size 64)** | $\sim 665{,}000\text{ items/sec}$ |
| **$P_{50}$ Latency** | $0.0016\text{ ms}$ |
| **$P_{90}$ Latency** | $0.0024\text{ ms}$ |
| **$P_{95}$ Latency** | $0.0033\text{ ms}$ |
| **Cache Hit Rate on Live Chat** | $\sim 99.9\%$ on synthetic chat stream |

### 3. Generate Evidently AI Drift Report
Run statistical drift tests comparing the reference baseline against current incoming production streams:

```bash
python -m ml.monitoring
```
Generates `api/static/drift_report.html` (interactive visual dashboard) and `api/static/drift_metrics.json`.

---

## Getting Started

### Prerequisites
- Docker & Docker Compose
- YouTube Data API Key

### Running with Docker

1. **Configure Environment:**
   Create a `.env` file in the root directory:
   ```env
   YOUTUBE_API_KEY=your_api_key_here
   ```

2. **Start all services:**
   ```bash
   docker compose up -d --build
   ```

3. **Open Interfaces:**
   - **Live Dashboard:** [http://localhost:3000](http://localhost:3000)
   - **FastAPI Docs:** [http://localhost:8000/docs](http://localhost:8000/docs)
   - **Evidently AI Drift Report:** [http://localhost:8000/v1/ml/drift-report](http://localhost:8000/v1/ml/drift-report)
   - **ML Engine Real-Time Stats:** [http://localhost:8000/v1/ml/stats](http://localhost:8000/v1/ml/stats)

---

## API Summary

- `POST /v1/track`: Start tracking a new YouTube Live video.
- `DELETE /v1/track/{video_id}`: Stop tracking and clear video data.
- `GET /v1/tracked`: List tracked videos and global aggregates.
- `GET /analytics`: Global sentiment metrics.
- `GET /v1/analytics/{video_id}`: Specific stream sentiment metrics.
- `GET /v1/ml/stats`: Real-time engine statistics (cache hit rate, $P_{95}$ latency, inference count).
- `GET /v1/ml/drift-report`: Interactive Evidently AI Data & Prediction Drift dashboard.
- `GET /v1/ml/drift-metrics`: JSON drift summary for automated monitoring.
- `WebSocket /live-feed`: Real-time streaming WebSocket of all processed sentiment records.
