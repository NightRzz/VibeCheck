from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import parse_qs, urlparse

import httpx

VIDEO_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{11}$")


class YouTubeApiError(RuntimeError):
    """Raised when the YouTube Data API returns an error response."""


class LiveChatEndedError(YouTubeApiError):
    """Raised when a live broadcast has ended or the live chat was not found."""


class InvalidPageTokenError(YouTubeApiError):
    """Raised when a continuation page token has expired or is invalid."""


@dataclass(frozen=True)
class YouTubeVideoMetadata:
    video_id: str
    title: str
    live_chat_id: str | None = None
    is_live: bool = False


@dataclass(frozen=True)
class YouTubeComment:
    comment_id: str
    video_id: str
    author: str | None
    text: str
    published_at: str


def extract_video_id(value: str) -> str | None:
    candidate = value.strip()
    if not candidate:
        return None

    if VIDEO_ID_PATTERN.fullmatch(candidate):
        return candidate

    parsed = urlparse(candidate)
    host = parsed.netloc.lower().removeprefix("www.")

    if host == "youtu.be":
        video_id = parsed.path.strip("/")
        return video_id if VIDEO_ID_PATTERN.fullmatch(video_id) else None

    if host in {"youtube.com", "m.youtube.com", "music.youtube.com"}:
        query = parse_qs(parsed.query)
        video_id = query.get("v", [None])[0]
        if video_id and VIDEO_ID_PATTERN.fullmatch(video_id):
            return video_id

        parts = [part for part in parsed.path.split("/") if part]
        if len(parts) >= 2 and parts[0] in {"embed", "live", "shorts", "v"}:
            video_id = parts[1]
            return video_id if VIDEO_ID_PATTERN.fullmatch(video_id) else None

    return None


def _extract_error_message(payload: dict[str, object]) -> str:
    error = payload.get("error")
    if isinstance(error, dict):
        message = error.get("message")
        if isinstance(message, str) and message:
            return message
    return "YouTube API request failed."


def _extract_error_reason(payload: dict[str, object]) -> str | None:
    error = payload.get("error")
    if not isinstance(error, dict):
        return None

    errors = error.get("errors")
    if not isinstance(errors, list):
        return None

    for item in errors:
        if not isinstance(item, dict):
            continue
        reason = item.get("reason")
        if isinstance(reason, str) and reason:
            return reason
def _safe_parse_json(response: httpx.Response) -> dict[str, object]:
    try:
        data = response.json()
        return data if isinstance(data, dict) else {}
    except Exception:
        raise YouTubeApiError(
            f"Non-JSON response from YouTube API (HTTP {response.status_code}): {response.text[:200]}"
        )


async def fetch_video_metadata(
    client: httpx.AsyncClient,
    api_base_url: str,
    api_key: str,
    video_id: str,
) -> YouTubeVideoMetadata:
    response = await client.get(
        f"{api_base_url}/videos",
        params={
            "part": "snippet,liveStreamingDetails",
            "id": video_id,
            "key": api_key,
        },
    )
    payload = _safe_parse_json(response)

    if response.status_code != 200:
        raise YouTubeApiError(_extract_error_message(payload))

    items = payload.get("items")
    if not isinstance(items, list) or not items:
        raise YouTubeApiError("Video was not found.")

    snippet = items[0].get("snippet", {})
    if not isinstance(snippet, dict):
        raise YouTubeApiError("Video metadata response was malformed.")

    title = snippet.get("title")
    if not isinstance(title, str) or not title:
        raise YouTubeApiError("Video title was missing from the API response.")

    live_details = items[0].get("liveStreamingDetails") or {}
    active_live_chat_id = live_details.get("activeLiveChatId")

    return YouTubeVideoMetadata(
        video_id=video_id,
        title=title,
        live_chat_id=active_live_chat_id if isinstance(active_live_chat_id, str) else None,
        is_live=bool(active_live_chat_id),
    )


async def fetch_recent_comments(
    client: httpx.AsyncClient,
    api_base_url: str,
    api_key: str,
    video_id: str,
    page_size: int,
) -> list[YouTubeComment]:
    response = await client.get(
        f"{api_base_url}/commentThreads",
        params={
            "part": "snippet",
            "videoId": video_id,
            "maxResults": page_size,
            "order": "time",
            "textFormat": "plainText",
            "key": api_key,
        },
    )
    payload = _safe_parse_json(response)

    if response.status_code != 200:
        if _extract_error_reason(payload) == "commentsDisabled":
            return []
        raise YouTubeApiError(_extract_error_message(payload))

    comments: list[YouTubeComment] = []
    items = payload.get("items")
    if not isinstance(items, list):
        return comments

    for item in items:
        if not isinstance(item, dict):
            continue

        thread_snippet = item.get("snippet", {})
        if not isinstance(thread_snippet, dict):
            continue

        comment = thread_snippet.get("topLevelComment", {})
        if not isinstance(comment, dict):
            continue

        comment_snippet = comment.get("snippet", {})
        if not isinstance(comment_snippet, dict):
            continue

        comment_id = comment.get("id")
        text = comment_snippet.get("textDisplay") or comment_snippet.get("textOriginal")
        published_at = comment_snippet.get("publishedAt")
        author = comment_snippet.get("authorDisplayName")

        if not isinstance(comment_id, str) or not comment_id:
            continue
        if not isinstance(text, str) or not text.strip():
            continue
        if not isinstance(published_at, str) or not published_at:
            continue

        comments.append(
            YouTubeComment(
                comment_id=comment_id,
                video_id=video_id,
                author=author if isinstance(author, str) and author else None,
                text=text.strip(),
                published_at=published_at,
            )
        )

    return comments


async def fetch_live_chat_messages(
    client: httpx.AsyncClient,
    api_base_url: str,
    api_key: str,
    video_id: str,
    live_chat_id: str,
    page_token: str | None = None,
    max_results: int = 200,
) -> tuple[list[YouTubeComment], str | None, int]:
    """Fetches real-time messages from YouTube Live Chat during an active broadcast.

    Enforces Google YouTube Data API schema constraint: 200 <= maxResults <= 2000.
    Returns:
        tuple of (comments_list, next_page_token, polling_interval_ms)
    """
    bounded_max_results = max(200, min(2000, max_results))
    params = {
        "part": "snippet,authorDetails",
        "liveChatId": live_chat_id,
        "maxResults": bounded_max_results,
        "key": api_key,
    }
    if page_token:
        params["pageToken"] = page_token

    response = await client.get(
        f"{api_base_url}/liveChat/messages",
        params=params,
    )
    payload = _safe_parse_json(response)

    if response.status_code != 200:
        error_reason = _extract_error_reason(payload)
        if error_reason in {"liveChatEnded", "liveChatNotFound"}:
            raise LiveChatEndedError(
                f"YouTube live stream chat has ended ({error_reason}) for video {video_id}."
            )
        if error_reason == "invalidPageToken":
            raise InvalidPageTokenError(
                f"Continuation page token expired or invalid for video {video_id}."
            )
        if error_reason == "rateLimitExceeded":
            return [], page_token, 5000
        raise YouTubeApiError(_extract_error_message(payload))

    next_page_token = payload.get("nextPageToken")
    polling_interval_ms = int(payload.get("pollingIntervalMillis", 2000))

    items = payload.get("items") or []
    comments: list[YouTubeComment] = []

    for item in items:
        if not isinstance(item, dict):
            continue

        snippet = item.get("snippet", {})
        author_details = item.get("authorDetails", {})

        msg_id = item.get("id")
        text = snippet.get("displayMessage")
        published_at = snippet.get("publishedAt")
        author = author_details.get("displayName")

        if not isinstance(msg_id, str) or not msg_id:
            continue
        if not isinstance(text, str) or not text.strip():
            continue
        if not isinstance(published_at, str) or not published_at:
            continue

        comments.append(
            YouTubeComment(
                comment_id=msg_id,
                video_id=video_id,
                author=author if isinstance(author, str) and author else None,
                text=text.strip(),
                published_at=published_at,
            )
        )

    return comments, next_page_token, polling_interval_ms
