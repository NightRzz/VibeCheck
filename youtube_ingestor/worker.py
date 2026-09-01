from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import httpx
from aiokafka import AIOKafkaProducer
from sqlalchemy import select, update

from config import settings
from database import SessionLocal, init_models
from models import TrackedVideo
from youtube_api import (
    InvalidPageTokenError,
    LiveChatEndedError,
    YouTubeApiError,
    YouTubeComment,
    fetch_live_chat_messages,
    fetch_recent_comments,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class RecentCommentCache:
    window: timedelta
    entries: dict[int, dict[str, datetime]]

    def has_recent(self, tracked_id: int, comment_id: str, now: datetime) -> bool:
        seen_at = self.entries.get(tracked_id, {}).get(comment_id)
        return seen_at is not None and now - seen_at <= self.window

    def remember(self, tracked_id: int, comment_id: str, now: datetime) -> None:
        self.entries.setdefault(tracked_id, {})[comment_id] = now

    def sync_active_videos(self, active_tracked_ids: set[int]) -> None:
        stale_video_ids = [
            tracked_id
            for tracked_id in self.entries
            if tracked_id not in active_tracked_ids
        ]
        for tracked_id in stale_video_ids:
            self.entries.pop(tracked_id, None)

    def prune(self, now: datetime) -> None:
        cutoff = now - self.window
        empty_video_ids: list[str] = []

        for tracked_id, comments in self.entries.items():
            stale_comment_ids = [
                comment_id
                for comment_id, seen_at in comments.items()
                if seen_at < cutoff
            ]
            for comment_id in stale_comment_ids:
                comments.pop(comment_id, None)
            if not comments:
                empty_video_ids.append(tracked_id)

        for tracked_id in empty_video_ids:
            self.entries.pop(tracked_id, None)


def serialize_message(value: dict[str, object]) -> bytes:
    return json.dumps(value, ensure_ascii=False).encode("utf-8")


async def load_active_videos() -> list[TrackedVideo]:
    async with SessionLocal() as session:
        result = await session.scalars(
            select(TrackedVideo)
            .where(TrackedVideo.is_active.is_(True))
            .order_by(TrackedVideo.added_at.asc())
        )
        return result.all()


async def publish_comment(
    producer: AIOKafkaProducer,
    video: TrackedVideo,
    comment: YouTubeComment,
) -> None:
    payload = {
        "source_id": f"youtube:{video.video_id}",
        "video_id": video.video_id,
        "external_id": comment.comment_id,
        "author": comment.author,
        "text": comment.text,
        "received_at": comment.published_at,
    }
    await producer.send_and_wait(settings.raw_vibe_topic, payload)


async def clear_video_live_chat(video_db_id: int) -> None:
    """Clears live_chat_id in the database when a live broadcast has ended."""
    try:
        async with SessionLocal() as session:
            await session.execute(
                update(TrackedVideo)
                .where(TrackedVideo.id == video_db_id)
                .values(live_chat_id=None)
            )
            await session.commit()
    except Exception as exc:
        logger.warning("Failed to clear live_chat_id for video db_id=%s: %s", video_db_id, exc)


async def poll_video(
    producer: AIOKafkaProducer,
    client: httpx.AsyncClient,
    video: TrackedVideo,
    cache: RecentCommentCache,
    live_chat_tokens: dict[int, str | None],
) -> int:
    now = datetime.now(timezone.utc)
    next_token: str | None = None

    if video.live_chat_id:
        page_token = live_chat_tokens.get(video.id)
        try:
            comments, next_token, _ = await fetch_live_chat_messages(
                client=client,
                api_base_url=settings.youtube_api_base_url,
                api_key=settings.youtube_api_key,
                video_id=video.video_id,
                live_chat_id=video.live_chat_id,
                page_token=page_token,
            )
            is_live = True
        except InvalidPageTokenError:
            logger.warning(
                "Continuation page token expired for video %s; resetting token for next cycle.",
                video.video_id,
            )
            live_chat_tokens.pop(video.id, None)
            return 0
        except LiveChatEndedError:
            logger.info(
                "Live stream chat ended for video %s; clearing live status and transitioning to archive comments.",
                video.video_id,
            )
            live_chat_tokens.pop(video.id, None)
            video.live_chat_id = None
            await clear_video_live_chat(video.id)
            comments = await fetch_recent_comments(
                client=client,
                api_base_url=settings.youtube_api_base_url,
                api_key=settings.youtube_api_key,
                video_id=video.video_id,
                page_size=settings.youtube_comment_page_size,
            )
            is_live = False
    else:
        # Standard Video / Archive: poll recent comments
        comments = await fetch_recent_comments(
            client=client,
            api_base_url=settings.youtube_api_base_url,
            api_key=settings.youtube_api_key,
            video_id=video.video_id,
            page_size=settings.youtube_comment_page_size,
        )
        is_live = False

    new_comments = [
        comment
        for comment in (comments if is_live else reversed(comments))
        if not cache.has_recent(video.id, comment.comment_id, now)
    ]

    # Publish to Kafka (if Kafka dispatch fails, token won't advance, preventing data loss)
    for comment in new_comments:
        await publish_comment(producer, video, comment)
        cache.remember(video.id, comment.comment_id, now)

    # Advance continuation token only after successful Kafka persistence
    if is_live and next_token:
        live_chat_tokens[video.id] = next_token

    return len(new_comments)


async def run() -> None:
    await init_models()
    producer = AIOKafkaProducer(
        bootstrap_servers=settings.kafka_bootstrap_servers,
        value_serializer=serialize_message,
    )
    cache = RecentCommentCache(
        window=timedelta(seconds=settings.youtube_seen_comment_window_seconds),
        entries={},
    )
    client = httpx.AsyncClient(timeout=settings.youtube_http_timeout_seconds)
    live_chat_tokens: dict[int, str | None] = {}

    await producer.start()
    try:
        while True:
            now = datetime.now(timezone.utc)
            # Prune expired cache entries once per polling loop, preventing per-item CPU starvation
            cache.prune(now)

            if not settings.youtube_api_key:
                logger.warning("YOUTUBE_API_KEY is not set. YouTube ingestor is idle.")
                await asyncio.sleep(settings.youtube_poll_interval_seconds)
                continue

            videos = await load_active_videos()
            active_ids = {video.id for video in videos}
            cache.sync_active_videos(active_ids)
            # Prune obsolete live chat tokens
            for stale_id in list(live_chat_tokens.keys()):
                if stale_id not in active_ids:
                    live_chat_tokens.pop(stale_id, None)

            if not videos:
                await asyncio.sleep(settings.youtube_poll_interval_seconds)
                continue

            results = await asyncio.gather(
                *[poll_video(producer, client, video, cache, live_chat_tokens) for video in videos],
                return_exceptions=True,
            )

            for video, result in zip(videos, results, strict=False):
                if isinstance(result, Exception):
                    if isinstance(result, YouTubeApiError):
                        logger.warning(
                            "YouTube poll failed for %s: %s",
                            video.video_id,
                            result,
                        )
                    else:
                        logger.error(
                            "Unexpected polling failure for %s: %s",
                            video.video_id,
                            result,
                            exc_info=(
                                type(result),
                                result,
                                result.__traceback__,
                            ),
                        )
                    continue

                if result:
                    logger.info(
                        "Published %s new YouTube comments for %s.",
                        result,
                        video.video_id,
                    )

            await asyncio.sleep(settings.youtube_poll_interval_seconds)
    finally:
        await client.aclose()
        await producer.stop()


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
