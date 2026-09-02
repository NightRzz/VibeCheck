from __future__ import annotations

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path

logger = logging.getLogger("api.main")

import httpx
from fastapi import Depends, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import Select, and_, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from database import SessionLocal, get_session, init_models
from models import Sentiment, TrackedVideo
from processor.sentiment_engine import SentimentEngine
from processor.worker import TELEMETRY_PATH
from ml.monitoring import REPORT_HTML_PATH, REPORT_JSON_PATH, generate_drift_report
from youtube_api import YouTubeApiError, extract_video_id, fetch_video_metadata

# Indexing Performance Gain
# \[
# \text{Sequential scan complexity} = O(N)
# \]
# \[
# \text{Indexed lookup complexity} = O(\log N)
# \]
# \[
# \frac{N}{\log_2(N)} = \frac{1{,}000{,}000}{\log_2(1{,}000{,}000)}
# \approx \frac{1{,}000{,}000}{20} = 50{,}000
# \]
# With a B-Tree index on \(video\_id\), the lookup is approximately
# \(50{,}000\times\) faster than a full sequential scan at \(N = 1{,}000{,}000\).


class Utf8JSONResponse(JSONResponse):
    media_type = "application/json; charset=utf-8"

    def render(self, content: object) -> bytes:
        return json.dumps(content, ensure_ascii=False, separators=(",", ":")).encode(
            "utf-8"
        )


class TrackVideoRequest(BaseModel):
    video: str = Field(..., min_length=1, max_length=500)


@asynccontextmanager
async def lifespan(_: FastAPI):
    await init_models()
    yield


app = FastAPI(
    title="VibeStream Dashboard",
    lifespan=lifespan,
    default_response_class=Utf8JSONResponse,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def serialize_sentiment(sentiment: Sentiment) -> dict[str, object]:
    return {
        "id": sentiment.id,
        "source_id": sentiment.source_id,
        "video_id": sentiment.video_id,
        "author": sentiment.author,
        "text": sentiment.text,
        "score": sentiment.score,
        "timestamp": sentiment.timestamp.isoformat(),
    }


def serialize_analytics(
    *,
    video_id: str | None,
    title: str | None,
    total_messages: int,
    average_score: float | None,
    min_score: float | None,
    max_score: float | None,
    recent: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "video_id": video_id,
        "title": title,
        "total_messages": total_messages,
        "average_score": average_score,
        "min_score": min_score,
        "max_score": max_score,
    }
    if recent is not None:
        payload["recent"] = recent
    return payload


def serialize_tracked_video_row(row: object) -> dict[str, object]:
    mapping = row._mapping
    average_score = mapping["average_score"]
    live_chat_id = mapping.get("live_chat_id")
    return {
        "id": mapping["id"],
        "video_id": mapping["video_id"],
        "title": mapping["title"],
        "is_active": mapping["is_active"],
        "is_live": bool(live_chat_id),
        "live_chat_id": live_chat_id,
        "added_at": mapping["added_at"].isoformat(),
        "message_count": int(mapping["message_count"] or 0),
        "average_score": float(average_score) if average_score is not None else None,
    }


def serialize_global_summary(rows: list[dict[str, object]]) -> dict[str, object]:
    active_rows = [row for row in rows if row["is_active"]]
    total_messages = sum(int(row["message_count"]) for row in active_rows)
    weighted_sum = sum(
        int(row["message_count"]) * float(row["average_score"] or 0)
        for row in active_rows
    )
    average_score = weighted_sum / total_messages if total_messages else None
    return {
        "total_messages": total_messages,
        "average_score": average_score,
    }


def sentiment_scope(
    video_id: str | None = None,
    *,
    active_only: bool = True,
) -> tuple[object | None, object | None, list[object]]:
    join_target = TrackedVideo
    join_condition = TrackedVideo.video_id == Sentiment.video_id
    filters: list[object] = []

    if active_only:
        join_condition = and_(join_condition, TrackedVideo.is_active.is_(True))

    if video_id is not None:
        filters.append(Sentiment.video_id == video_id)

    return join_target, join_condition, filters


async def fetch_analytics_summary(
    session: AsyncSession,
    video_id: str | None = None,
    *,
    active_only: bool = True,
) -> tuple[int, float | None, float | None, float | None]:
    join_target, join_condition, filters = sentiment_scope(
        video_id,
        active_only=active_only,
    )
    query = select(
        func.count(Sentiment.id),
        func.avg(Sentiment.score),
        func.min(Sentiment.score),
        func.max(Sentiment.score),
    ).select_from(Sentiment)

    if join_target is not None and join_condition is not None:
        query = query.join(join_target, join_condition)

    for clause in filters:
        query = query.where(clause)

    result = await session.execute(query)
    total_messages, average_score, min_score, max_score = result.one()
    return (
        int(total_messages or 0),
        float(average_score) if average_score is not None else None,
        float(min_score) if min_score is not None else None,
        float(max_score) if max_score is not None else None,
    )


async def fetch_recent_sentiments(
    session: AsyncSession,
    video_id: str | None = None,
    limit: int = 12,
    *,
    active_only: bool = True,
) -> list[dict[str, object]]:
    join_target, join_condition, filters = sentiment_scope(
        video_id,
        active_only=active_only,
    )
    query: Select[tuple[Sentiment]] = select(Sentiment).order_by(
        Sentiment.timestamp.desc()
    )

    if join_target is not None and join_condition is not None:
        query = query.join(join_target, join_condition)

    query = query.limit(limit)

    for clause in filters:
        query = query.where(clause)

    result = await session.scalars(query)
    return [serialize_sentiment(item) for item in result.all()]


async def get_tracked_video_or_404(
    session: AsyncSession,
    video_id: str,
) -> TrackedVideo:
    tracked = await session.scalar(
        select(TrackedVideo).where(TrackedVideo.video_id == video_id)
    )
    if tracked is None:
        raise HTTPException(status_code=404, detail="Tracked video was not found.")
    return tracked


@app.get("/analytics")
async def analytics(
    session: AsyncSession = Depends(get_session),
) -> dict[str, object]:
    total_messages, average_score, min_score, max_score = await fetch_analytics_summary(
        session
    )
    recent_items = await fetch_recent_sentiments(session)
    return serialize_analytics(
        video_id=None,
        title="Global View",
        total_messages=total_messages,
        average_score=average_score,
        min_score=min_score,
        max_score=max_score,
        recent=recent_items,
    )


@app.get("/v1/analytics/{video_id}")
async def video_analytics(
    video_id: str,
    session: AsyncSession = Depends(get_session),
) -> dict[str, object]:
    tracked = await get_tracked_video_or_404(session, video_id)
    total_messages, average_score, min_score, max_score = await fetch_analytics_summary(
        session,
        video_id=video_id,
        active_only=False,
    )
    
    # We will also fetch recent sentiments for this specific video here
    recent_items = await fetch_recent_sentiments(session, video_id=video_id, limit=50, active_only=False)

    return serialize_analytics(
        video_id=tracked.video_id,
        title=tracked.title,
        total_messages=total_messages,
        average_score=average_score,
        min_score=min_score,
        max_score=max_score,
        recent=recent_items,
    )


@app.post("/v1/track")
@app.options("/v1/track")
async def track_video(
    payload: TrackVideoRequest = None, # type: ignore
    session: AsyncSession = Depends(get_session),
) -> dict[str, object]:
    if payload is None:
        return {}
    if not settings.youtube_api_key:
        raise HTTPException(
            status_code=503,
            detail="YOUTUBE_API_KEY is not configured.",
        )

    video_id = extract_video_id(payload.video)
    if video_id is None:
        raise HTTPException(status_code=400, detail="Invalid YouTube URL or video ID.")

    async with httpx.AsyncClient(
        timeout=settings.youtube_http_timeout_seconds
    ) as client:
        try:
            metadata = await fetch_video_metadata(
                client=client,
                api_base_url=settings.youtube_api_base_url,
                api_key=settings.youtube_api_key,
                video_id=video_id,
            )
        except YouTubeApiError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    tracked = await session.scalar(
        select(TrackedVideo).where(TrackedVideo.video_id == metadata.video_id)
    )
    if tracked is None:
        tracked = TrackedVideo(
            video_id=metadata.video_id,
            title=metadata.title,
            is_active=True,
            live_chat_id=metadata.live_chat_id,
        )
        session.add(tracked)
    else:
        tracked.title = metadata.title
        tracked.is_active = True
        tracked.live_chat_id = metadata.live_chat_id

    await session.commit()
    await session.refresh(tracked)
    return {
        "id": tracked.id,
        "video_id": tracked.video_id,
        "title": tracked.title,
        "is_active": tracked.is_active,
        "is_live": bool(tracked.live_chat_id),
        "live_chat_id": tracked.live_chat_id,
        "added_at": tracked.added_at.isoformat(),
    }


@app.get("/v1/tracked")
async def list_tracked_videos(
    session: AsyncSession = Depends(get_session),
) -> dict[str, object]:
    query = (
        select(
            TrackedVideo.id,
            TrackedVideo.video_id,
            TrackedVideo.title,
            TrackedVideo.is_active,
            TrackedVideo.live_chat_id,
            TrackedVideo.added_at,
            func.count(Sentiment.id).label("message_count"),
            func.avg(Sentiment.score).label("average_score"),
        )
        .select_from(TrackedVideo)
        .outerjoin(Sentiment, Sentiment.video_id == TrackedVideo.video_id)
        .group_by(
            TrackedVideo.id,
            TrackedVideo.video_id,
            TrackedVideo.title,
            TrackedVideo.is_active,
            TrackedVideo.live_chat_id,
            TrackedVideo.added_at,
        )
        .order_by(TrackedVideo.is_active.desc(), TrackedVideo.added_at.desc())
    )
    result = await session.execute(query)
    items = [serialize_tracked_video_row(row) for row in result.all()]
    return {
        "items": items,
        "global": serialize_global_summary(items),
    }


@app.delete("/v1/track/{video_id}")
async def delete_tracked_video(
    video_id: str,
    session: AsyncSession = Depends(get_session),
) -> dict[str, object]:
    await get_tracked_video_or_404(session, video_id)
    await session.execute(delete(Sentiment).where(Sentiment.video_id == video_id))
    await session.execute(delete(TrackedVideo).where(TrackedVideo.video_id == video_id))
    await session.commit()
    return {"deleted": True, "video_id": video_id}


@app.websocket("/live-feed/{video_id}")
async def live_feed_by_video(websocket: WebSocket, video_id: str) -> None:
    await websocket.accept()
    param = websocket.query_params.get("last_seen_id")
    if param is not None:
        try:
            last_seen_id = max(int(param), 0)
        except ValueError:
            last_seen_id = 0
    else:
        async with SessionLocal() as session:
            max_id = await session.scalar(
                select(func.max(Sentiment.id)).where(Sentiment.video_id == video_id)
            )
            last_seen_id = max_id or 0

    try:
        while True:
            async with SessionLocal() as session:
                query = (
                    select(Sentiment)
                    .join(
                        TrackedVideo,
                        and_(
                            TrackedVideo.video_id == Sentiment.video_id,
                            TrackedVideo.is_active.is_(True),
                        ),
                    )
                    .where(Sentiment.id > last_seen_id)
                    .where(Sentiment.video_id == video_id)
                    .order_by(Sentiment.id.asc())
                    .limit(settings.live_feed_batch_size)
                )
                result = await session.scalars(query)
                updates = result.all()

            for item in updates:
                await websocket.send_json(serialize_sentiment(item))
                last_seen_id = item.id

            await asyncio.sleep(settings.live_feed_poll_interval_seconds)
    except WebSocketDisconnect:
        return


@app.websocket("/live-feed")
async def live_feed(websocket: WebSocket) -> None:
    await websocket.accept()
    param = websocket.query_params.get("last_seen_id")
    if param is not None:
        try:
            last_seen_id = max(int(param), 0)
        except ValueError:
            last_seen_id = 0
    else:
        async with SessionLocal() as session:
            max_id = await session.scalar(select(func.max(Sentiment.id)))
            last_seen_id = max_id or 0

    try:
        while True:
            async with SessionLocal() as session:
                result = await session.scalars(
                    select(Sentiment)
                    .join(
                        TrackedVideo,
                        and_(
                            TrackedVideo.video_id == Sentiment.video_id,
                            TrackedVideo.is_active.is_(True),
                        ),
                    )
                    .where(Sentiment.id > last_seen_id)
                    .order_by(Sentiment.id.asc())
                    .limit(settings.live_feed_batch_size)
                )
                updates = result.all()

            for item in updates:
                await websocket.send_json(serialize_sentiment(item))
                last_seen_id = item.id

            await asyncio.sleep(settings.live_feed_poll_interval_seconds)
    except WebSocketDisconnect:
        return


_ML_ENGINE: SentimentEngine | None = None
_DRIFT_LOCK = asyncio.Lock()


def get_engine_singleton() -> SentimentEngine:
    global _ML_ENGINE
    if _ML_ENGINE is None:
        _ML_ENGINE = SentimentEngine()
    return _ML_ENGINE


async def _fetch_current_sentiments(session: AsyncSession, limit: int = 1000):
    try:
        result = await session.execute(
            select(Sentiment.text, Sentiment.score).order_by(Sentiment.timestamp.desc()).limit(limit)
        )
        rows = result.all()
        import pandas as pd
        return pd.DataFrame([{"text": r[0], "score": r[1]} for r in rows])
    except Exception as exc:
        logger.warning("Could not fetch sentiments from database: %s", exc)
        import pandas as pd
        return pd.DataFrame()


@app.get("/v1/ml/stats")
async def ml_engine_stats() -> dict[str, object]:
    """Returns real-time inference latency percentiles and LRU cache efficiency metrics.
    
    Prefers live worker telemetry recorded across process boundaries.
    """
    if TELEMETRY_PATH.exists():
        try:
            return json.loads(TELEMETRY_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass

    try:
        engine = get_engine_singleton()
        return engine.get_metrics()
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=503,
            detail="ML model pipeline artifact not initialized. Run 'python -m ml.train'.",
        ) from exc


@app.get("/v1/ml/drift-report", response_class=FileResponse)
async def get_drift_report(
    refresh: bool = False,
    session: AsyncSession = Depends(get_session),
) -> FileResponse:
    """Serves the latest Evidently AI Data & Prediction Drift interactive HTML dashboard.
    
    Generates reports in an asynchronous worker thread to prevent event-loop starvation.
    """
    if refresh or not REPORT_HTML_PATH.exists():
        async with _DRIFT_LOCK:
            if refresh or not REPORT_HTML_PATH.exists():
                try:
                    current_df = await _fetch_current_sentiments(session)
                    await asyncio.to_thread(generate_drift_report, current_df=current_df)
                except FileNotFoundError as exc:
                    raise HTTPException(
                        status_code=503,
                        detail="Reference baseline dataset not found. Run 'python -m ml.train'.",
                    ) from exc
                except Exception as exc:
                    raise HTTPException(
                        status_code=500,
                        detail=f"Failed to generate drift report: {exc}",
                    ) from exc
    return FileResponse(REPORT_HTML_PATH, media_type="text/html")


@app.get("/v1/ml/drift-metrics")
async def get_drift_metrics(
    refresh: bool = False,
    session: AsyncSession = Depends(get_session),
) -> dict[str, object]:
    """Returns Evidently AI drift detection summary in JSON for automated health monitoring."""
    if refresh or not REPORT_JSON_PATH.exists():
        async with _DRIFT_LOCK:
            if refresh or not REPORT_JSON_PATH.exists():
                try:
                    current_df = await _fetch_current_sentiments(session)
                    await asyncio.to_thread(generate_drift_report, current_df=current_df)
                except FileNotFoundError as exc:
                    raise HTTPException(
                        status_code=503,
                        detail="Reference baseline dataset not found. Run 'python -m ml.train'.",
                    ) from exc
                except Exception as exc:
                    raise HTTPException(
                        status_code=500,
                        detail=f"Failed to generate drift metrics: {exc}",
                    ) from exc

    if REPORT_JSON_PATH.exists():
        try:
            return json.loads(REPORT_JSON_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"status": "generated", "path": str(REPORT_JSON_PATH)}

