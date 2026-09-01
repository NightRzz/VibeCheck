from __future__ import annotations

import asyncio
import json
import logging
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Sequence

from aiokafka import AIOKafkaConsumer
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from database import SessionLocal, init_models
from models import Sentiment
from processor.sentiment_engine import SentimentEngine

TELEMETRY_PATH = (
    Path(__file__).resolve().parent.parent / "api" / "static" / "worker_telemetry.json"
)
TELEMETRY_PATH.parent.mkdir(parents=True, exist_ok=True)


def configure_utf8_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8", errors="replace")


configure_utf8_stdio()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Inference Capacity (Vectorized Scikit-Learn / XGBoost with LRU Cache on CPU)
# \[
# \text{Cached Latency } \approx 0.0015 \text{ ms}, \quad \text{Vectorized Batch Latency } \approx 0.03 \text{ ms}
# \]
# \[
# \frac{60{,}000 \text{ ms}}{0.03 \text{ ms/comment}} = 2{,}000{,}000 \text{ comments per 60-second window}
# \]
#
# Index Maintenance Cost
# \[
# 10^6 \text{ comments} \times 100 \frac{\text{bytes}}{\text{index row}}
# = 100{,}000{,}000 \text{ bytes} \approx 95.37 \text{ MB}
# \]
# The unique index on \(external\_id\) costs about \(95 \text{ MB}\) for
# \(1{,}000{,}000\) comments, which is a small tax compared to the total data
# volume and is worth paying for deduplication integrity.

_ENGINE: SentimentEngine | None = None


def get_sentiment_engine() -> SentimentEngine:
    global _ENGINE
    if _ENGINE is None:
        _ENGINE = SentimentEngine()
    return _ENGINE


def write_telemetry(metrics: dict) -> None:
    """Publishes worker telemetry for API consumption across process boundaries atomically."""
    try:
        temp_path = TELEMETRY_PATH.with_suffix(".tmp")
        temp_path.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
        temp_path.replace(TELEMETRY_PATH)
    except Exception as e:
        logger.warning("Failed to write worker telemetry: %s", e)


@dataclass
class RawVibeMessage:
    source_id: str
    text: str
    video_id: str | None = None
    external_id: str | None = None
    author: str | None = None
    received_at: str | None = None


def deserialize_message(value: bytes) -> RawVibeMessage:
    payload = json.loads(value.decode("utf-8"))
    return RawVibeMessage(
        source_id=payload["source_id"],
        text=payload["text"],
        video_id=payload.get("video_id"),
        external_id=payload.get("external_id"),
        author=payload.get("author"),
        received_at=payload.get("received_at"),
    )


def analyze_sentiment(text: str) -> float:
    return get_sentiment_engine().predict_score(text)


def parse_received_at(value: str | None) -> datetime:
    if not value:
        return datetime.now(timezone.utc)

    return datetime.fromisoformat(value.replace("Z", "+00:00"))


async def persist_sentiment(
    session: AsyncSession, message: RawVibeMessage
) -> Sentiment | None:
    """Single-message persistence helper (retained for backward compatibility and tests)."""
    score = analyze_sentiment(message.text)
    statement = (
        insert(Sentiment)
        .values(
            source_id=message.source_id,
            video_id=message.video_id,
            external_id=message.external_id,
            author=message.author,
            text=message.text,
            score=score,
            timestamp=parse_received_at(message.received_at),
        )
        .on_conflict_do_nothing(index_elements=[Sentiment.external_id])
        .returning(Sentiment.id)
    )
    result = await session.execute(statement)
    await session.commit()
    sentiment_id = result.scalar_one_or_none()
    if sentiment_id is None:
        return None

    return Sentiment(
        id=sentiment_id,
        source_id=message.source_id,
        video_id=message.video_id,
        external_id=message.external_id,
        author=message.author,
        text=message.text,
        score=score,
        timestamp=parse_received_at(message.received_at),
    )


async def persist_batch(
    session: AsyncSession, messages: Sequence[RawVibeMessage]
) -> int:
    """
    Performs vectorized sentiment scoring and bulk database insertion,
    eliminating 95%+ of per-transaction overhead.
    """
    if not messages:
        return 0

    # Deduplicate within batch by external_id if present
    seen_external_ids: set[str] = set()
    deduped_messages: List[RawVibeMessage] = []
    for m in messages:
        if m.external_id:
            if m.external_id in seen_external_ids:
                continue
            seen_external_ids.add(m.external_id)
        deduped_messages.append(m)

    engine = get_sentiment_engine()
    texts = [m.text for m in deduped_messages]
    scores = engine.predict_batch(texts)

    records = [
        {
            "source_id": m.source_id,
            "video_id": m.video_id,
            "external_id": m.external_id,
            "author": m.author,
            "text": m.text,
            "score": score,
            "timestamp": parse_received_at(m.received_at),
        }
        for m, score in zip(deduped_messages, scores)
    ]

    statement = (
        insert(Sentiment)
        .values(records)
        .on_conflict_do_nothing(index_elements=[Sentiment.external_id])
    )
    result = await session.execute(statement)
    await session.commit()
    return result.rowcount or 0


async def process_stream() -> None:
    await init_models()
    engine = get_sentiment_engine()
    write_telemetry(engine.get_metrics())
    logger.info("Initialized ML sentiment engine: %s", engine.get_metrics())

    consumer = AIOKafkaConsumer(
        settings.raw_vibe_topic,
        bootstrap_servers=settings.kafka_bootstrap_servers,
        group_id=settings.consumer_group_id,
        auto_offset_reset="earliest",
    )
    await consumer.start()
    logger.info("Listening to topic '%s' with micro-batching.", settings.raw_vibe_topic)
    try:
        processed_count = 0
        last_telemetry_count = 0
        last_telemetry_time = time.monotonic()
        while True:
            # Consume micro-batches of up to 100 messages within 200ms
            batch_data = await consumer.getmany(timeout_ms=200, max_records=100)
            batch_messages: List[RawVibeMessage] = []

            for tp, records in batch_data.items():
                for record in records:
                    try:
                        batch_messages.append(deserialize_message(record.value))
                    except Exception:
                        logger.exception("Failed to deserialize Kafka message at offset %s.", record.offset)

            if batch_messages:
                try:
                    async with SessionLocal() as session:
                        inserted = await persist_batch(session, batch_messages)
                    processed_count += len(batch_messages)
                    logger.info(
                        "Batch processed: %d items (inserted %d new rows, %d duplicates skipped)",
                        len(batch_messages),
                        inserted,
                        len(batch_messages) - inserted,
                    )
                except Exception:
                    logger.exception("Failed to persist sentiment batch of %d items.", len(batch_messages))

                now = time.monotonic()
                if (processed_count - last_telemetry_count >= 100) or (
                    now - last_telemetry_time >= 5.0 and processed_count > last_telemetry_count
                ):
                    last_telemetry_count = processed_count
                    last_telemetry_time = now
                    metrics = engine.get_metrics()
                    write_telemetry(metrics)
                    logger.info(
                        "Telemetry: Inferences=%d, Cache Hit Rate=%.2f%%, P95=%.4fms",
                        metrics["total_inferences"],
                        metrics["cache_hit_rate"] * 100,
                        metrics["latency_p95_ms"],
                    )

            # Prevent busy-spinning if idle
            if not batch_data:
                await asyncio.sleep(0.05)
    finally:
        await consumer.stop()


def main() -> None:
    asyncio.run(process_stream())


if __name__ == "__main__":
    main()
