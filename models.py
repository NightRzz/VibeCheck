from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, Text, func
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


class Sentiment(Base):
    __tablename__ = "sentiments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        server_default=func.now(),
    )
