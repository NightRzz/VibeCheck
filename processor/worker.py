from __future__ import annotations

import asyncio
import json
import logging
import sys
from dataclasses import dataclass
from datetime import datetime, timezone

from aiokafka import AIOKafkaConsumer
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from textblob import TextBlob

from config import settings
from database import SessionLocal, init_models
from models import Sentiment


def configure_utf8_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8", errors="replace")


configure_utf8_stdio()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Inference Capacity
# \[
# \frac{60{,}000 \text{ ms}}{50 \text{ ms/comment}} = 1{,}200 \text{ comments per 60-second window}
# \]
#
# Index Maintenance Cost
# \[
# 10^6 \text{ comments} \times 100 \frac{\text{bytes}}{\text{index row}}
# = 100{,}000{,}000 \text{ bytes}
# \]
# \[
# 100{,}000{,}000 \text{ bytes} \times \frac{1 \text{ MB}}{1024^2 \text{ bytes}}
# \approx 95.37 \text{ MB}
# \]
# The unique index on \(external\_id\) costs about \(95 \text{ MB}\) for
# \(1{,}000{,}000\) comments, which is a small tax compared to the total data
# volume and is worth paying for deduplication integrity.


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
    return float(TextBlob(text).sentiment.polarity)


def parse_received_at(value: str | None) -> datetime:
    if not value:
        return datetime.now(timezone.utc)

    return datetime.fromisoformat(value.replace("Z", "+00:00"))


async def persist_sentiment(
    session: AsyncSession, message: RawVibeMessage
) -> Sentiment | None:
    statement = (
        insert(Sentiment)
        .values(
            source_id=message.source_id,
            video_id=message.video_id,
            external_id=message.external_id,
            author=message.author,
            text=message.text,
            score=analyze_sentiment(message.text),
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

    return await session.get(Sentiment, sentiment_id)


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
                if saved is None:
                    logger.info(
                        "Skipped duplicate sentiment external_id=%s source_id=%s",
                        payload.external_id,
                        payload.source_id,
                    )
                    continue
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
