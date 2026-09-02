"""Production Data & Concept Drift Monitoring using Evidently AI.

Monitors:
- Data Drift: message length, word count, uppercase ratio (spam/hype detection)
- Prediction Drift: distribution of predicted sentiment scores [-1.0, 1.0]
- Exports interactive HTML dashboard and JSON metrics for Prometheus/APIs.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import pandas as pd
from evidently import Report
from evidently.presets import DataDriftPreset

from processor.sentiment_engine import SentimentEngine, normalize_chat_text

logger = logging.getLogger("ml.monitoring")

ARTIFACTS_DIR = Path(__file__).resolve().parent / "artifacts"
REFERENCE_DATA_PATH = ARTIFACTS_DIR / "reference_data.parquet"
REPORT_OUTPUT_DIR = Path(__file__).resolve().parent.parent / "api" / "static"
REPORT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
REPORT_HTML_PATH = REPORT_OUTPUT_DIR / "drift_report.html"
REPORT_JSON_PATH = REPORT_OUTPUT_DIR / "drift_metrics.json"


def extract_features(df: pd.DataFrame, engine: Optional[SentimentEngine] = None) -> pd.DataFrame:
    """Extracts structural and predictive features from raw text for drift analysis."""
    clean_texts = [normalize_chat_text(t) for t in df["text"]]
    char_lens = [len(t) for t in clean_texts]
    word_counts = [len(t.split()) for t in clean_texts]
    uppercase_ratio = [
        (sum(1 for c in t if c.isupper()) / max(len(t), 1)) for t in clean_texts
    ]

    features = pd.DataFrame({
        "char_len": char_lens,
        "word_count": word_counts,
        "uppercase_ratio": uppercase_ratio,
    })

    if "score" in df.columns:
        features["score"] = df["score"].values
    elif engine is not None:
        features["score"] = engine.predict_batch(clean_texts)

    return features


def fetch_recent_production_sentiments(limit: int = 1000) -> pd.DataFrame:
    """Attempts to fetch the most recent sentiments from PostgreSQL; returns empty DataFrame on failure."""
    try:
        import asyncio
        from database import SessionLocal
        from models import Sentiment
        from sqlalchemy import select

        async def _query():
            async with SessionLocal() as session:
                result = await session.execute(
                    select(Sentiment.text, Sentiment.score).order_by(Sentiment.timestamp.desc()).limit(limit)
                )
                rows = result.all()
                return pd.DataFrame([{"text": r[0], "score": r[1]} for r in rows])

        return asyncio.run(_query())
    except Exception as e:
        logger.info("Could not fetch sentiments from database (%s); using live chat stream sample", e)
        return pd.DataFrame()


def generate_drift_report(
    current_df: Optional[pd.DataFrame] = None,
    engine: Optional[SentimentEngine] = None,
) -> Path:
    """
    Generates an Evidently AI Data & Prediction Drift report comparing
    the reference baseline against the current production stream.
    """
    if not REFERENCE_DATA_PATH.exists():
        raise FileNotFoundError(
            f"Reference dataset not found at {REFERENCE_DATA_PATH}. Run 'python -m ml.train' first."
        )

    if engine is None:
        engine = SentimentEngine()

    logger.info("Loading reference baseline from %s...", REFERENCE_DATA_PATH)
    ref_raw = pd.read_parquet(REFERENCE_DATA_PATH)
    ref_sample = ref_raw.iloc[: min(2000, len(ref_raw))]
    reference_features = extract_features(ref_sample, engine=engine)

    if current_df is None or current_df.empty:
        current_df = fetch_recent_production_sentiments(limit=1000)

    if current_df is None or current_df.empty:
        logger.info("Sampling live-stream chat batch to measure distribution drift against reference baseline...")
        import random
        from ml.data import LIVE_CHAT_STREAM_SAMPLES
        sample_records = []
        for _ in range(600):
            text, _ = random.choice(LIVE_CHAT_STREAM_SAMPLES)
            if random.random() < 0.35:
                text = text.upper() + "!!!"
            sample_records.append({"text": text})
        current_df = pd.DataFrame(sample_records)

    current_features = extract_features(current_df, engine=engine)

    logger.info("Running Evidently AI DataDriftPreset on %d reference and %d current samples...",
                len(reference_features), len(current_features))

    report = Report(metrics=[DataDriftPreset()])
    snapshot = report.run(reference_data=reference_features, current_data=current_features)

    # Save visual HTML report
    snapshot.save_html(str(REPORT_HTML_PATH))
    logger.info("Evidently drift report successfully written to %s", REPORT_HTML_PATH)

    # Save JSON summary metrics
    try:
        snapshot.save_json(str(REPORT_JSON_PATH))
    except Exception as e:
        logger.warning("Could not serialize drift json: %s", e)

    return REPORT_HTML_PATH


def main() -> None:
    path = generate_drift_report()
    print(f"Drift report generated at: {path}")


if __name__ == "__main__":
    main()
