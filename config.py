from __future__ import annotations

import os
from dataclasses import dataclass


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


settings = Settings()
