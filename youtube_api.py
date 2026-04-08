from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import parse_qs, urlparse

import httpx

VIDEO_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{11}$")


class YouTubeApiError(RuntimeError):
    """Raised when the YouTube Data API returns an error response."""


@dataclass(frozen=True)
class YouTubeVideoMetadata:
    video_id: str
    title: str


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
    return None


async def fetch_video_metadata(
    client: httpx.AsyncClient,
    api_base_url: str,
    api_key: str,
    video_id: str,
) -> YouTubeVideoMetadata:
    response = await client.get(
        f"{api_base_url}/videos",
        params={
            "part": "snippet",
            "id": video_id,
            "key": api_key,
        },
    )
    payload = response.json()

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

    return YouTubeVideoMetadata(video_id=video_id, title=title)


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
    payload = response.json()

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
