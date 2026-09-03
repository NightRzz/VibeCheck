"""Unit tests for YouTube Live Chat and video ingestion API."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from youtube_api import (
    InvalidPageTokenError,
    LiveChatEndedError,
    YouTubeApiError,
    YouTubeVideoMetadata,
    extract_video_id,
    fetch_live_chat_messages,
    fetch_video_metadata,
)
from youtube_ingestor.worker import RecentCommentCache


def test_extract_video_id_from_live_url():
    live_url = "https://www.youtube.com/live/jfKfPfyJRdk?si=abc"
    assert extract_video_id(live_url) == "jfKfPfyJRdk"

    watch_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    assert extract_video_id(watch_url) == "dQw4w9WgXcQ"

    short_url = "https://youtu.be/dQw4w9WgXcQ"
    assert extract_video_id(short_url) == "dQw4w9WgXcQ"


@pytest.mark.asyncio
async def test_fetch_video_metadata_with_live_chat():
    mock_payload = {
        "items": [
            {
                "snippet": {"title": "Lofi Hip Hop Live Stream"},
                "liveStreamingDetails": {
                    "activeLiveChatId": "chat_abc123_live",
                    "actualStartTime": "2026-09-01T00:00:00Z",
                },
            }
        ]
    }

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = mock_payload
    mock_client.get.return_value = mock_response

    metadata = await fetch_video_metadata(
        client=mock_client,
        api_base_url="https://www.googleapis.com/youtube/v3",
        api_key="fake_key",
        video_id="jfKfPfyJRdk",
    )

    assert metadata.video_id == "jfKfPfyJRdk"
    assert metadata.title == "Lofi Hip Hop Live Stream"
    assert metadata.is_live is True
    assert metadata.live_chat_id == "chat_abc123_live"


@pytest.mark.asyncio
async def test_fetch_live_chat_messages_schema_and_pagination():
    mock_chat_payload = {
        "nextPageToken": "token_page_2",
        "pollingIntervalMillis": 1500,
        "items": [
            {
                "id": "msg_001",
                "snippet": {
                    "displayMessage": "Massive W streamer!",
                    "publishedAt": "2026-09-04T00:20:00Z",
                },
                "authorDetails": {
                    "displayName": "Gamer123",
                },
            },
            {
                "id": "msg_002",
                "snippet": {
                    "displayMessage": "poggers in the chat",
                    "publishedAt": "2026-09-04T00:20:01Z",
                },
                "authorDetails": {
                    "displayName": "PogChamp",
                },
            },
        ],
    }

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = mock_chat_payload
    mock_client.get.return_value = mock_response

    comments, next_token, interval = await fetch_live_chat_messages(
        client=mock_client,
        api_base_url="https://www.googleapis.com/youtube/v3",
        api_key="fake_key",
        video_id="jfKfPfyJRdk",
        live_chat_id="chat_abc123_live",
        max_results=50,  # Requesting below 200 should be bounded up to 200
    )

    # Verify query parameters respected Google YouTube Data API schema
    called_params = mock_client.get.call_args[1]["params"]
    assert called_params["maxResults"] == 200  # Enforced minimum
    assert len(comments) == 2
    assert comments[0].text == "Massive W streamer!"
    assert next_token == "token_page_2"
    assert interval == 1500


@pytest.mark.asyncio
async def test_fetch_live_chat_ended_error():
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_response = MagicMock()
    mock_response.status_code = 403
    mock_response.json.return_value = {
        "error": {
            "errors": [{"reason": "liveChatEnded", "message": "The live chat has ended."}],
            "message": "The live chat has ended.",
        }
    }
    mock_client.get.return_value = mock_response

    with pytest.raises(LiveChatEndedError):
        await fetch_live_chat_messages(
            client=mock_client,
            api_base_url="https://www.googleapis.com/youtube/v3",
            api_key="fake_key",
            video_id="jfKfPfyJRdk",
            live_chat_id="chat_ended_123",
        )


@pytest.mark.asyncio
async def test_fetch_live_chat_invalid_page_token_error():
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_response = MagicMock()
    mock_response.status_code = 400
    mock_response.json.return_value = {
        "error": {
            "errors": [{"reason": "invalidPageToken", "message": "The page token is invalid."}],
            "message": "The page token is invalid.",
        }
    }
    mock_client.get.return_value = mock_response

    with pytest.raises(InvalidPageTokenError):
        await fetch_live_chat_messages(
            client=mock_client,
            api_base_url="https://www.googleapis.com/youtube/v3",
            api_key="fake_key",
            video_id="jfKfPfyJRdk",
            live_chat_id="chat_123",
            page_token="stale_token",
        )


@pytest.mark.asyncio
async def test_fetch_video_metadata_non_json_error():
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_response = MagicMock()
    mock_response.status_code = 502
    mock_response.json.side_effect = ValueError("Non-JSON response")
    mock_response.text = "<html>502 Bad Gateway</html>"
    mock_client.get.return_value = mock_response

    with pytest.raises(YouTubeApiError) as exc_info:
        await fetch_video_metadata(
            client=mock_client,
            api_base_url="https://www.googleapis.com/youtube/v3",
            api_key="fake_key",
            video_id="jfKfPfyJRdk",
        )
    assert "502" in str(exc_info.value)


def test_recent_comment_cache_prune_and_lookup():
    now = datetime.now(timezone.utc)
    cache = RecentCommentCache(window=timedelta(seconds=60), entries={})

    cache.remember(tracked_id=1, comment_id="c_1", now=now)
    assert cache.has_recent(tracked_id=1, comment_id="c_1", now=now) is True
    assert cache.has_recent(tracked_id=1, comment_id="c_2", now=now) is False

    # Simulate 70 seconds later
    future = now + timedelta(seconds=70)
    assert cache.has_recent(tracked_id=1, comment_id="c_1", now=future) is False

    # Prune should remove expired entry cleanly
    cache.prune(future)
    assert 1 not in cache.entries
