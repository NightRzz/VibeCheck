from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from database import SessionLocal, get_session, init_models
from models import Sentiment

INDEX_FILE = Path(__file__).with_name("index.html")


@asynccontextmanager
async def lifespan(_: FastAPI):
    await init_models()
    yield


app = FastAPI(title="VibeStream Dashboard", lifespan=lifespan)


def serialize_sentiment(sentiment: Sentiment) -> dict[str, object]:
    return {
        "id": sentiment.id,
        "source_id": sentiment.source_id,
        "text": sentiment.text,
        "score": sentiment.score,
        "timestamp": sentiment.timestamp.isoformat(),
    }


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(INDEX_FILE)


@app.get("/analytics")
async def analytics(
    session: AsyncSession = Depends(get_session),
) -> dict[str, object]:
    summary = await session.execute(
        select(
            func.count(Sentiment.id),
            func.avg(Sentiment.score),
            func.min(Sentiment.score),
            func.max(Sentiment.score),
        )
    )
    total_messages, average_score, min_score, max_score = summary.one()

    recent_query = await session.scalars(
        select(Sentiment).order_by(Sentiment.timestamp.desc()).limit(10)
    )
    recent_items = [serialize_sentiment(item) for item in recent_query.all()]

    return {
        "total_messages": total_messages,
        "average_score": float(average_score) if average_score is not None else None,
        "min_score": float(min_score) if min_score is not None else None,
        "max_score": float(max_score) if max_score is not None else None,
        "recent": recent_items,
    }


@app.websocket("/live-feed")
async def live_feed(websocket: WebSocket) -> None:
    await websocket.accept()
    last_seen_id = 0

    try:
        while True:
            async with SessionLocal() as session:
                result = await session.scalars(
                    select(Sentiment)
                    .where(Sentiment.id > last_seen_id)
                    .order_by(Sentiment.id.asc())
                    .limit(25)
                )
                updates = result.all()

            for item in updates:
                await websocket.send_json(serialize_sentiment(item))
                last_seen_id = item.id

            await asyncio.sleep(1)
    except WebSocketDisconnect:
        return
