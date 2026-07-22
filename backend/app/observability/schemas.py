from __future__ import annotations

from pydantic import BaseModel


class MetricsResponse(BaseModel):
    ai_calls_total: int
    ai_calls_fallback: int
    ai_fallback_rate: float
    error: str | None = None
