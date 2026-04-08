from __future__ import annotations

import os
from dataclasses import dataclass


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default

    try:
        return int(value)
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None:
        return default

    try:
        return float(value)
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://vibecheck:vibecheck@localhost:5432/vibecheck",
    )
    kafka_bootstrap_servers: str = os.getenv(
        "KAFKA_BOOTSTRAP_SERVERS",
        "localhost:9094",
    )
    raw_vibe_topic: str = os.getenv("RAW_VIBE_TOPIC", "raw-vibe-data")
    consumer_group_id: str = os.getenv("KAFKA_CONSUMER_GROUP", "vibecheck-workers")
    youtube_api_base_url: str = os.getenv(
        "YOUTUBE_API_BASE_URL",
        "https://www.googleapis.com/youtube/v3",
    )
    youtube_api_key: str = os.getenv("YOUTUBE_API_KEY", "")
    youtube_poll_interval_seconds: int = _env_int(
        "YOUTUBE_POLL_INTERVAL_SECONDS",
        15,
    )
    youtube_comment_page_size: int = _env_int("YOUTUBE_COMMENT_PAGE_SIZE", 50)
    youtube_seen_comment_window_seconds: int = _env_int(
        "YOUTUBE_SEEN_COMMENT_WINDOW_SECONDS",
        3600,
    )
    youtube_http_timeout_seconds: int = _env_int(
        "YOUTUBE_HTTP_TIMEOUT_SECONDS",
        15,
    )
    live_feed_poll_interval_seconds: float = _env_float(
        "LIVE_FEED_POLL_INTERVAL_SECONDS",
        0.25,
    )
    live_feed_batch_size: int = _env_int("LIVE_FEED_BATCH_SIZE", 25)


settings = Settings()
