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

### 1. Model Evaluation & MLflow Experiment Tracking
Evaluate the Contextual Transformer on the academic **`cardiffnlp/tweet_eval`** test benchmark, log hyperparameters and metrics to MLflow, and package ONNX configurations:

```bash
python -m ml.train
```

View the MLflow tracking dashboard:
```bash
mlflow ui --port 5000
```

#### Academic Benchmark Comparison (`cardiffnlp/tweet_eval` SemEval)
| Model Architecture | Runtime | Macro F1 | Accuracy | Context & Negation Aware? | Inference Latency |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **TF-IDF + Logistic Regression** | CPU (sklearn) | $56.0\%$ | $55.0\%$ | No (Bag-of-Words) | $0.001\text{ ms}$ |
| **TF-IDF + XGBoost** | CPU (xgboost) | $53.2\%$ | $52.8\%$ | No (Bag-of-Words) | $0.003\text{ ms}$ |
| **Twitter-RoBERTa-base (Production)** | **ONNX Runtime (INT8)** | **$72.1\%\text{–}74.6\%$** | **$72.1\%\text{–}74.6\%$** | **Yes (Self-Attention)** | **$8\text{–}15\text{ ms}$** *(Uncached)*<br>**$0.001\text{ ms}$** *(Cached)* |

---

### 2. Profile & Benchmark CPU Inference Latency
Run the standalone CPU latency and throughput benchmark suite with real-time stream simulation and semantic negation verification:

```bash
python -m ml.evaluate
```

#### Benchmark Results (WSL2 CPU):
| Metric | Measurement | Description |
| :--- | :--- | :--- |
| **LRU Cache Hit Latency ($P_{50}$)** | **$0.0014\text{ ms}$** | Repeated chatter (`W`, `L`, `poggers`, chat emoticons) served instantly |
| **LRU Cache Hit Latency ($P_{95}$)** | **$0.0027\text{ ms}$** | Tail latency for cached streaming tokens |
| **Cached Throughput** | **$>134{,}000\text{ items/sec}$** | Single-core CPU throughput on live stream chat |
| **Uncached Transformer Latency** | **$8\text{–}15\text{ ms}$** | Quantized INT8 forward pass on modern CPU (No GPU needed) |
| **Cache Hit Rate on Live Chat** | **$>99\%$** | Effective cache utilization on high-frequency streaming chatter |

#### Semantic Context & Negation Handling Verification:
| Test Input | Predicted Score | Direction | Context Handling |
| :--- | :--- | :--- | :--- |
| `"not bad"` | **$+0.1668$** | Positive | Resolves classical Bag-of-Words negation failure |
| `"actually not bad at all"` | **$+0.6767$** | Positive | Understands complex multi-token modifier |
| `"not good"` | **$-0.4176$** | Negative | Inverts positive token to negative sentiment |
| `"not great, pretty boring"` | **$-0.8189$** | Negative | Accumulates compound negative sentiment |
| `"huge W streamer"` | **$+0.7860$** | Positive | Domain slang mapping (`W` $\to$ Win) |
| `"massive W in the chat!"` | **$+0.9062$** | Positive | Full live chat idiom recognition |

---

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
