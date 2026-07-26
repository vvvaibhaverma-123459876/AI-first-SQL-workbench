"""The RQ job body for a fired scheduled query -- also called directly
(not via the queue) by the "run now" route for immediate feedback, so
there is exactly one implementation of "what running this schedule means."
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime

from app.connections import service as connections_service
from app.connections.models import DataConnection
from app.scheduled_queries.models import ScheduledQuery
from app.scheduled_queries.notify import send_email, send_webhook


def _condition_met(row: ScheduledQuery, row_count: int) -> bool:
    if row.condition == "always":
        return True
    if row.condition == "threshold":
        return row_count > (row.condition_value or 0)
    if row.condition == "diff":
        if row.last_row_count is None:
            return True  # nothing to diff against yet -- treat the first run as a change
        return abs(row_count - row.last_row_count) >= (row.condition_value or 1)
    return False


def run_scheduled_query(scheduled_query_id: str) -> dict:
    from app.db.control_plane_sync import get_sync_session

    session = get_sync_session()
    try:
        row = session.get(ScheduledQuery, uuid.UUID(scheduled_query_id))
        if row is None:
            return {"status": "not_found"}

        connection = session.get(DataConnection, row.connection_id)
        if connection is None:
            row.last_run_at = datetime.utcnow()
            row.last_status = "error: connection no longer exists"
            session.commit()
            return {"status": row.last_status}

        # Re-validated here too, not just at creation/update: a connection
        # is mutable (its connector_type could change), and this runs
        # fully unattended -- never trust a stored SQL string without
        # re-checking it's still provably read-only.
        if not connections_service.is_read_only_sql(row.sql, connector_type=connection.connector_type):
            row.last_run_at = datetime.utcnow()
            row.last_status = "error: SQL is no longer provably read-only"
            session.commit()
            return {"status": row.last_status}

        try:
            result = connections_service.run_query_sync(connection, row.sql)
        except Exception as exc:
            row.last_run_at = datetime.utcnow()
            row.last_status = f"query failed: {exc}"
            session.commit()
            return {"status": row.last_status}

        row_count = result.row_count
        status_parts: list[str] = []
        notified = False

        if _condition_met(row, row_count):
            if row.notify_webhook_url:
                # Query results can contain datetime/Decimal values requests'
                # own json= encoder can't serialize -- normalize through the
                # same json.dumps(default=str) pattern ai_service.py already
                # uses for the investigate agent's sample rows.
                sample_rows = json.loads(json.dumps(result.rows[:5], default=str))
                payload = {
                    "scheduled_query_id": str(row.id),
                    "name": row.name,
                    "condition": row.condition,
                    "row_count": row_count,
                    "columns": result.columns,
                    "sample_rows": sample_rows,
                    "fired_at": datetime.utcnow().isoformat(),
                }
                ok, detail = send_webhook(row.notify_webhook_url, payload)
                status_parts.append("notified via webhook" if ok else detail or "webhook failed")
                notified = notified or ok
            if row.notify_email:
                subject = f"Scheduled query fired: {row.name}"
                body = f"{row.name!r} returned {row_count} row(s).\n\nSQL:\n{row.sql}"
                ok, detail = send_email(row.notify_email, subject, body)
                status_parts.append("notified via email" if ok else detail or "email failed")
                notified = notified or ok
            if not row.notify_webhook_url and not row.notify_email:
                status_parts.append("condition met but no webhook/email configured")
            if notified:
                row.last_notified_at = datetime.utcnow()
        else:
            status_parts.append("ok (condition not met)")

        row.last_run_at = datetime.utcnow()
        row.last_row_count = row_count
        row.last_status = "; ".join(status_parts) if status_parts else "ok"
        session.commit()
        return {"status": row.last_status, "row_count": row_count}
    finally:
        session.close()
