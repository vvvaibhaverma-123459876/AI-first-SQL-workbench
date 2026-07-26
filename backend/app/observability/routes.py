from __future__ import annotations

from fastapi import APIRouter

from app.observability.metrics import get_ai_fallback_metrics
from app.observability.schemas import MetricsResponse

router = APIRouter(tags=["observability"])


@router.get("/metrics", response_model=MetricsResponse)
def get_metrics() -> MetricsResponse:
    # Unauthenticated, same posture as /health and /ai/status -- aggregate
    # counts only, no per-user or per-workspace detail, meant to be scraped.
    return MetricsResponse(**get_ai_fallback_metrics())
