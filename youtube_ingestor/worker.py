from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import httpx
from aiokafka import AIOKafkaProducer
from sqlalchemy import select

from config import settings
from database import SessionLocal, init_models
from models import TrackedVideo
from youtube_api import YouTubeApiError, YouTubeComment, fetch_recent_comments

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class RecentCommentCache:
    window: timedelta
    entries: dict[str, dict[str, datetime]]

    def has_recent(self, video_id: str, comment_id: str, now: datetime) -> bool:
        self.prune(now)
        seen_at = self.entries.get(video_id, {}).get(comment_id)
        return seen_at is not None and now - seen_at <= self.window

    def remember(self, video_id: str, comment_id: str, now: datetime) -> None:
        self.entries.setdefault(video_id, {})[comment_id] = now

    def sync_active_videos(self, active_video_ids: set[str]) -> None:
        stale_video_ids = [
            video_id for video_id in self.entries if video_id not in active_video_ids
        ]
        for video_id in stale_video_ids:
            self.entries.pop(video_id, None)

    def prune(self, now: datetime) -> None:
        cutoff = now - self.window
        empty_video_ids: list[str] = []

        for video_id, comments in self.entries.items():
            stale_comment_ids = [
                comment_id
                for comment_id, seen_at in comments.items()
                if seen_at < cutoff
            ]
            for comment_id in stale_comment_ids:
                comments.pop(comment_id, None)
            if not comments:
                empty_video_ids.append(video_id)

        for video_id in empty_video_ids:
            self.entries.pop(video_id, None)


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
        "author": comment.author,
        "text": comment.text,
        "received_at": comment.published_at,
    }
    await producer.send_and_wait(settings.raw_vibe_topic, payload)


async def poll_video(
    producer: AIOKafkaProducer,
    client: httpx.AsyncClient,
    video: TrackedVideo,
    cache: RecentCommentCache,
) -> int:
    comments = await fetch_recent_comments(
        client=client,
        api_base_url=settings.youtube_api_base_url,
        api_key=settings.youtube_api_key,
        video_id=video.video_id,
        page_size=settings.youtube_comment_page_size,
    )
    now = datetime.now(timezone.utc)
    new_comments = [
        comment
        for comment in reversed(comments)
        if not cache.has_recent(video.video_id, comment.comment_id, now)
    ]

    for comment in new_comments:
        await publish_comment(producer, video, comment)
        cache.remember(video.video_id, comment.comment_id, now)

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

    await producer.start()
    try:
        while True:
            if not settings.youtube_api_key:
                logger.warning("YOUTUBE_API_KEY is not set. YouTube ingestor is idle.")
                await asyncio.sleep(settings.youtube_poll_interval_seconds)
                continue

            videos = await load_active_videos()
            cache.sync_active_videos({video.video_id for video in videos})
            if not videos:
                await asyncio.sleep(settings.youtube_poll_interval_seconds)
                continue

            results = await asyncio.gather(
                *[poll_video(producer, client, video, cache) for video in videos],
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
