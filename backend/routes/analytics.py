import json

from flask import Blueprint, jsonify

from db import get_db
from auth import require_staff_login
from analytics import run_weekly_analytics_job
from rate_limit import limiter

analytics_bp = Blueprint("analytics", __name__)


def _get_latest_analytics():
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "SELECT stats_json, summary_text, generated_at FROM weekly_analytics ORDER BY id DESC LIMIT 1"
    )
    row = cur.fetchone()
    conn.close()

    if not row:
        return {"stats": None, "summary": None, "generated_at": None}

    try:
        stats = json.loads(row["stats_json"])
    except (ValueError, TypeError):
        # Defensive on principle (this is our own json.dumps() output, so a parse
        # failure here would mean corrupted data, not a malformed AI response) -
        # never leave a bare json.loads unguarded in new code, the way
        # routes/health.py currently does.
        stats = None

    return {
        "stats": stats,
        "summary": row["summary_text"],
        "generated_at": row["generated_at"],
    }


@analytics_bp.route("/api/analytics/weekly", methods=["GET"])
@require_staff_login
def get_weekly_analytics():
    return jsonify(_get_latest_analytics())


@analytics_bp.route("/api/analytics/weekly/recompute", methods=["POST"])
@require_staff_login
@limiter.limit("5 per minute")
def recompute_weekly_analytics():
    """Manual trigger for testing/on-demand use - the scheduled job (app.py) runs
    this same function automatically on a weekly cadence."""
    run_weekly_analytics_job()
    return jsonify(_get_latest_analytics()), 201
