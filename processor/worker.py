from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from aiokafka import AIOKafkaConsumer
from sqlalchemy.ext.asyncio import AsyncSession
from textblob import TextBlob

from config import settings
from database import SessionLocal, init_models
from models import Sentiment

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Inference Capacity
# \[
# \frac{60{,}000 \text{ ms}}{50 \text{ ms/comment}} = 1{,}200 \text{ comments per 60-second window}
# \]


@dataclass
class RawVibeMessage:
    source_id: str
    text: str
    received_at: str | None = None


def deserialize_message(value: bytes) -> RawVibeMessage:
    payload = json.loads(value.decode("utf-8"))
    return RawVibeMessage(
        source_id=payload["source_id"],
        text=payload["text"],
        received_at=payload.get("received_at"),
    )


def analyze_sentiment(text: str) -> float:
    return float(TextBlob(text).sentiment.polarity)


async def persist_sentiment(
    session: AsyncSession, message: RawVibeMessage
) -> Sentiment:
    sentiment = Sentiment(
        source_id=message.source_id,
        text=message.text,
        score=analyze_sentiment(message.text),
        timestamp=(
            datetime.fromisoformat(message.received_at)
            if message.received_at
            else datetime.now(timezone.utc)
        ),
    )
    session.add(sentiment)
    await session.commit()
    await session.refresh(sentiment)
    return sentiment


async def process_stream() -> None:
    await init_models()
    consumer = AIOKafkaConsumer(
        settings.raw_vibe_topic,
        bootstrap_servers=settings.kafka_bootstrap_servers,
        group_id=settings.consumer_group_id,
        auto_offset_reset="earliest",
    )
    await consumer.start()
    logger.info("Listening to topic '%s'.", settings.raw_vibe_topic)
    try:
        async for message in consumer:
            try:
                payload = deserialize_message(message.value)
                async with SessionLocal() as session:
                    saved = await persist_sentiment(session, payload)
                logger.info(
                    "Stored sentiment id=%s source_id=%s score=%.3f",
                    saved.id,
                    saved.source_id,
                    saved.score,
                )
            except Exception:
                logger.exception(
                    "Failed to process Kafka message at offset %s.", message.offset
                )
    finally:
        await consumer.stop()


def main() -> None:
    asyncio.run(process_stream())


if __name__ == "__main__":
    main()
