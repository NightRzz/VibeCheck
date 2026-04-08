from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    func,
    text as sql_text,
)
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Storage Budget
# \[
# 500 \frac{\text{vibes}}{\text{hour}} \times 24 \frac{\text{hours}}{\text{day}}
# = 12{,}000 \frac{\text{vibes}}{\text{day}}
# \]
# \[
# 12{,}000 \frac{\text{vibes}}{\text{day}} \times 30 \text{ days}
# = 360{,}000 \text{ vibes}
# \]
# \[
# 360{,}000 \text{ vibes} \times 1 \frac{\text{KB}}{\text{row}}
# = 360{,}000 \text{ KB}
# \]
# \[
# 360{,}000 \text{ KB} \times \frac{1 \text{ MB}}{1024 \text{ KB}}
# \approx 351.56 \text{ MB}
# \]
# Using decimal units instead, \(360{,}000 \text{ KB} \div 1000 = 360 \text{ MB}\).


class Base(AsyncAttrs, DeclarativeBase):
    """Base class for async SQLAlchemy models."""


class TrackedVideo(Base):
    __tablename__ = "tracked_videos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    video_id: Mapped[str] = mapped_column(
        String(32), nullable=False, unique=True, index=True
    )
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        index=True,
        server_default=sql_text("true"),
    )
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class Sentiment(Base):
    __tablename__ = "sentiments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    video_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    external_id: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        unique=True,
    )
    author: Mapped[str | None] = mapped_column(String(255), nullable=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        server_default=func.now(),
    )
