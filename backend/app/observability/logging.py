"""Structured (JSON) logging setup. No new dependency: a small stdlib
logging.Formatter subclass covers the actual bar here ("structured logs"),
and this project's established discipline is not to reach for a library
(structlog, python-json-logger) when a ~15-line formatter does the job."""
from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone

_RESERVED = frozenset(logging.LogRecord(None, 0, "", 0, "", (), None).__dict__.keys()) | {"message", "asctime"}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        # Anything passed via logging's `extra={...}` kwarg lands as plain
        # attributes on the record -- surface those too, not just the
        # formatted message string.
        for key, value in record.__dict__.items():
            if key not in _RESERVED and key not in payload:
                payload[key] = value
        return json.dumps(payload, default=str)


def configure_logging() -> None:
    root = logging.getLogger()
    if any(isinstance(h, logging.StreamHandler) and getattr(h, "_ai_sql_studio_json", False) for h in root.handlers):
        return  # idempotent -- app.main can be imported multiple times in one process (tests do this)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    handler._ai_sql_studio_json = True  # type: ignore[attr-defined]
    root.handlers = [handler]
    root.setLevel(logging.INFO)
