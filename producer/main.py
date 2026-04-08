from __future__ import annotations

import json
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from aiokafka import AIOKafkaProducer
from fastapi import FastAPI, HTTPException, Request, status
from pydantic import BaseModel, Field

from config import settings

# Ingestion Throughput
# \[
# \frac{1000 \text{ ms}}{2 \text{ ms/message}} = 500 \text{ messages/second}
# \]


class IngestRequest(BaseModel):
    source_id: str = Field(..., min_length=1, max_length=255)
    text: str = Field(..., min_length=1)


def serialize_message(value: dict[str, str]) -> bytes:
    return json.dumps(value).encode("utf-8")


@asynccontextmanager
async def lifespan(app: FastAPI):
    producer = AIOKafkaProducer(
        bootstrap_servers=settings.kafka_bootstrap_servers,
        value_serializer=serialize_message,
    )
    await producer.start()
    app.state.kafka_producer = producer
    try:
        yield
    finally:
        await producer.stop()


app = FastAPI(title="VibeStream Ingestor", lifespan=lifespan)


@app.post("/ingest", status_code=status.HTTP_202_ACCEPTED)
async def ingest_vibe(payload: IngestRequest, request: Request) -> dict[str, object]:
    producer: AIOKafkaProducer | None = getattr(
        request.app.state, "kafka_producer", None
    )
    if producer is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Kafka producer is not available.",
        )

    event = {
        "source_id": payload.source_id,
        "text": payload.text.strip(),
        "received_at": datetime.now(timezone.utc).isoformat(),
    }
    metadata = await producer.send_and_wait(settings.raw_vibe_topic, event)
    return {
        "topic": metadata.topic,
        "partition": metadata.partition,
        "offset": metadata.offset,
        "accepted": True,
    }
