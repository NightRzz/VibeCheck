"""Comprehensive regression test suite for core VibeCheck contracts and backward compatibility.

Uses per-test scoped in-memory database and httpx.AsyncClient with ASGITransport to
prevent event-loop deadlocks and dialect conflicts under pytest-asyncio.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from api.main import (
    app,
    get_session,
    serialize_analytics,
    serialize_global_summary,
    serialize_sentiment,
)
from models import Base, Sentiment, TrackedVideo
from processor.worker import (
    RawVibeMessage,
    analyze_sentiment,
    deserialize_message,
    parse_received_at,
    persist_batch,
    persist_sentiment,
)
from youtube_api import YouTubeVideoMetadata


@pytest_asyncio.fixture
async def test_env():
    """Creates an isolated, per-test in-memory database bound strictly to the current test event loop."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
        echo=False,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async def override_get_session():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session

    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client, session_factory

    app.dependency_overrides.clear()
    await engine.dispose()


# ---------------------------------------------------------------------------
# 1. Backward Compatibility of Worker Contracts & Serialization (Unit Tests)
# ---------------------------------------------------------------------------


def test_regression_deserialize_raw_vibe_message():
    payload = {
        "source_id": "youtube:abc12345678",
        "video_id": "abc12345678",
        "external_id": "comment_999",
        "author": "StreamFan",
        "text": "Huge W in the chat!",
        "received_at": "2026-09-04T00:00:00Z",
    }
    raw_bytes = json.dumps(payload).encode("utf-8")
    msg = deserialize_message(raw_bytes)

    assert isinstance(msg, RawVibeMessage)
    assert msg.source_id == "youtube:abc12345678"
    assert msg.video_id == "abc12345678"
    assert msg.author == "StreamFan"
    assert msg.text == "Huge W in the chat!"


def test_regression_analyze_sentiment_contract():
    score_pos = analyze_sentiment("Massive W play, brilliant!")
    score_neg = analyze_sentiment("L streamer, terrible and boring")

    assert isinstance(score_pos, float)
    assert isinstance(score_neg, float)
    assert score_pos > 0.3
    assert score_neg < -0.3


def test_regression_parse_received_at():
    dt = parse_received_at("2026-09-04T00:00:00Z")
    assert dt.tzinfo is not None
    assert dt.year == 2026

    dt_fallback = parse_received_at(None)
    assert dt_fallback.tzinfo is not None


def test_regression_serialize_sentiment():
    now = datetime.now(timezone.utc)
    s = Sentiment(
        id=1,
        source_id="youtube:vid1",
        video_id="vid1",
        external_id="ext1",
        author="Alice",
        text="Poggers!",
        score=0.85,
        timestamp=now,
    )
    serialized = serialize_sentiment(s)

    assert serialized["id"] == 1
    assert serialized["video_id"] == "vid1"
    assert serialized["author"] == "Alice"
    assert serialized["text"] == "Poggers!"
    assert serialized["score"] == 0.85
    assert serialized["timestamp"] == now.isoformat()


def test_regression_serialize_global_summary():
    rows = [
        {"is_active": True, "message_count": 10, "average_score": 0.5},
        {"is_active": True, "message_count": 20, "average_score": -0.2},
        {"is_active": False, "message_count": 50, "average_score": 0.9},
    ]
    summary = serialize_global_summary(rows)

    assert summary["total_messages"] == 30
    expected_avg = (10 * 0.5 + 20 * -0.2) / 30
    assert summary["average_score"] == pytest.approx(expected_avg, 0.0001)


# ---------------------------------------------------------------------------
# 2. Worker Persistence Regression (Mocked Session to isolate PostgreSQL dialect)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_regression_persist_single_sentiment_contract():
    mock_session = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = 42
    mock_session.execute.return_value = mock_result

    msg = RawVibeMessage(
        source_id="youtube:vid1",
        video_id="vid1",
        external_id="comm_001",
        author="Tester",
        text="Nice stream!",
        received_at="2026-09-04T00:00:00Z",
    )
    saved = await persist_sentiment(mock_session, msg)

    assert saved is not None
    assert saved.id == 42
    assert saved.external_id == "comm_001"
    assert saved.score > 0.0
    assert mock_session.execute.called
    assert mock_session.commit.called


@pytest.mark.asyncio
async def test_regression_persist_batch_contract():
    mock_session = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.rowcount = 3
    mock_session.execute.return_value = mock_result

    msgs = [
        RawVibeMessage(source_id="s1", video_id="v1", external_id="e1", text="W"),
        RawVibeMessage(source_id="s2", video_id="v1", external_id="e2", text="L"),
        RawVibeMessage(source_id="s3", video_id="v1", external_id="e3", text="pog"),
    ]
    inserted = await persist_batch(mock_session, msgs)

    assert inserted == 3
    assert mock_session.execute.called
    assert mock_session.commit.called


# ---------------------------------------------------------------------------
# 3. Core FastAPI Route Regressions (Scoped Async Test Client & DB)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_regression_get_analytics_empty(test_env):
    client, _ = test_env
    response = await client.get("/analytics")
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Global View"
    assert data["total_messages"] == 0
    assert data["average_score"] is None
    assert data["recent"] == []


@pytest.mark.asyncio
async def test_regression_get_analytics_with_data(test_env):
    client, session_factory = test_env
    async with session_factory() as session:
        video = TrackedVideo(video_id="test_vid_123", title="Test Stream", is_active=True)
        session.add(video)
        session.add_all([
            Sentiment(
                source_id="youtube:test_vid_123",
                video_id="test_vid_123",
                external_id="c_1",
                author="UserA",
                text="Great game!",
                score=0.8,
                timestamp=datetime.now(timezone.utc),
            ),
            Sentiment(
                source_id="youtube:test_vid_123",
                video_id="test_vid_123",
                external_id="c_2",
                author="UserB",
                text="Horrible lag!",
                score=-0.7,
                timestamp=datetime.now(timezone.utc),
            ),
        ])
        await session.commit()

    # Test global analytics
    response = await client.get("/analytics")
    assert response.status_code == 200
    data = response.json()
    assert data["total_messages"] == 2
    assert len(data["recent"]) == 2
    assert data["min_score"] == pytest.approx(-0.7, 0.01)
    assert data["max_score"] == pytest.approx(0.8, 0.01)

    # Test single video analytics
    vid_resp = await client.get("/v1/analytics/test_vid_123")
    assert vid_resp.status_code == 200
    vid_data = vid_resp.json()
    assert vid_data["video_id"] == "test_vid_123"
    assert vid_data["total_messages"] == 2


@pytest.mark.asyncio
async def test_regression_get_video_analytics_not_found(test_env):
    client, _ = test_env
    response = await client.get("/v1/analytics/non_existent_vid")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_regression_track_lifecycle_and_cascade_delete(test_env):
    client, _ = test_env
    valid_vid_id = "dQw4w9WgXcQ"
    mock_meta = YouTubeVideoMetadata(
        video_id=valid_vid_id,
        title="Sample Video",
        live_chat_id="chat_99",
        is_live=True,
    )

    from dataclasses import replace
    from config import settings

    mock_settings = replace(settings, youtube_api_key="mock_key")
    with (
        patch("api.main.settings", mock_settings),
        patch("api.main.fetch_video_metadata", new=AsyncMock(return_value=mock_meta)),
    ):
        track_resp = await client.post("/v1/track", json={"video": f"https://www.youtube.com/watch?v={valid_vid_id}"})
        assert track_resp.status_code == 200
        track_data = track_resp.json()
        assert track_data["video_id"] == valid_vid_id
        assert track_data["is_live"] is True
        assert track_data["live_chat_id"] == "chat_99"

    # Verify video appears in /v1/tracked
    list_resp = await client.get("/v1/tracked")
    assert list_resp.status_code == 200
    list_data = list_resp.json()
    assert len(list_data["items"]) == 1
    assert list_data["items"][0]["video_id"] == valid_vid_id
    assert list_data["items"][0]["is_live"] is True

    # Delete tracked video
    del_resp = await client.delete(f"/v1/track/{valid_vid_id}")
    assert del_resp.status_code == 200

    # Verify deletion reflected in /v1/tracked
    list_after = await client.get("/v1/tracked")
    assert len(list_after.json()["items"]) == 0
