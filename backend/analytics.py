import os
import json
import logging
from datetime import date, datetime, timedelta, timezone
from anthropic import Anthropic

from db import get_db

logger = logging.getLogger(__name__)

WINDOW_DAYS = 7
MODEL = "claude-haiku-4-5-20251001"

FALLBACK_SUMMARY = "Weekly summary unavailable, raw stats below are still accurate"

_client = None


def get_client():
    global _client
    if _client is None:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        _client = Anthropic(api_key=api_key)
    return _client


def compute_weekly_stats(window_days=WINDOW_DAYS):
    """Raw stats over a trailing window_days-day window ending today (inclusive
    on both ends, so the default 7 covers today and the 6 days before it).

    Date-range filtering matches the SUBSTR(created_at, 1, 10) convention already
    used in routes/patients.py's list_patients, rather than a raw datetime range.

    average_wait_minutes uses COALESCE(actual_wait, estimated_wait) per visit:
    actual_wait is the ground-truth measurement but is only populated once a visit
    reaches 'completed' (see routes/visits.py's update_status); estimated_wait is
    the prediction made at check-in/assignment time and is set for nearly every
    visit regardless of outcome. Falling back to it keeps still-in-progress,
    no-show, and otherwise never-completed visits in the average instead of
    silently dropping them.
    """
    window_end = date.today()
    window_start = window_end - timedelta(days=window_days - 1)
    window_start_str = window_start.isoformat()
    window_end_str = window_end.isoformat()

    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT COUNT(*) AS count FROM visits
        WHERE SUBSTR(created_at, 1, 10) >= ? AND SUBSTR(created_at, 1, 10) <= ?
        """,
        (window_start_str, window_end_str),
    )
    total_visits = cur.fetchone()["count"]

    cur.execute(
        """
        SELECT AVG(COALESCE(actual_wait, estimated_wait)) AS avg_wait
        FROM visits
        WHERE SUBSTR(created_at, 1, 10) >= ? AND SUBSTR(created_at, 1, 10) <= ?
          AND COALESCE(actual_wait, estimated_wait) IS NOT NULL
        """,
        (window_start_str, window_end_str),
    )
    avg_wait = cur.fetchone()["avg_wait"]
    average_wait_minutes = round(avg_wait, 1) if avg_wait is not None else None

    cur.execute(
        """
        SELECT
            SUM(CASE WHEN booked_slot_time IS NOT NULL THEN 1 ELSE 0 END) AS booked_count,
            SUM(CASE WHEN booked_slot_time IS NULL THEN 1 ELSE 0 END) AS walkin_count
        FROM visits
        WHERE SUBSTR(created_at, 1, 10) >= ? AND SUBSTR(created_at, 1, 10) <= ?
        """,
        (window_start_str, window_end_str),
    )
    split_row = cur.fetchone()
    booked_count = split_row["booked_count"] or 0
    walkin_count = split_row["walkin_count"] or 0

    cur.execute(
        """
        SELECT v.doctor_id, d.name AS doctor_name, COUNT(*) AS count
        FROM visits v
        LEFT JOIN doctors d ON v.doctor_id = d.id
        WHERE SUBSTR(v.created_at, 1, 10) >= ? AND SUBSTR(v.created_at, 1, 10) <= ?
        GROUP BY v.doctor_id
        ORDER BY count DESC
        """,
        (window_start_str, window_end_str),
    )
    visits_per_doctor = [
        {"doctor_name": row["doctor_name"] or "Unassigned", "count": row["count"]}
        for row in cur.fetchall()
    ]

    cur.execute(
        """
        SELECT
            SUM(CASE WHEN status = 'no_show' THEN 1 ELSE 0 END) AS no_show_count,
            SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) AS completed_count
        FROM visits
        WHERE SUBSTR(created_at, 1, 10) >= ? AND SUBSTR(created_at, 1, 10) <= ?
        """,
        (window_start_str, window_end_str),
    )
    status_row = cur.fetchone()
    no_show_count = status_row["no_show_count"] or 0
    completed_count = status_row["completed_count"] or 0

    conn.close()

    return {
        "window_start": window_start_str,
        "window_end": window_end_str,
        "total_visits": total_visits,
        "average_wait_minutes": average_wait_minutes,
        "walkin_count": walkin_count,
        "booked_count": booked_count,
        "visits_per_doctor": visits_per_doctor,
        "no_show_count": no_show_count,
        "completed_count": completed_count,
    }


def _build_summary_prompt(stats):
    return (
        "You are writing a short, plain-language weekly summary for clinic staff at a "
        "Calgary walk-in clinic. Base it ONLY on the stats below - do not invent any "
        "number, day-of-week pattern, or trend that isn't directly supported by this data "
        "(it does not include a day-by-day breakdown, so never claim a specific day was "
        "busiest).\n\n"
        f"Window: {stats['window_start']} to {stats['window_end']}\n"
        f"Total visits: {stats['total_visits']}\n"
        f"Average wait time: {stats['average_wait_minutes']} minutes\n"
        f"Walk-in visits: {stats['walkin_count']}\n"
        f"Booked visits: {stats['booked_count']}\n"
        f"No-shows: {stats['no_show_count']}\n"
        f"Completed visits: {stats['completed_count']}\n"
        f"Visits per doctor: {json.dumps(stats['visits_per_doctor'])}\n\n"
        "Write 2-4 short sentences highlighting whatever is actually notable in these "
        "numbers (e.g. one doctor carrying a much larger share of visits, a no-show count "
        "worth flagging, a wait time that stands out). Be concrete and reference the actual "
        "numbers. No markdown formatting. Respond with ONLY the summary text, no preamble."
    )


def _extract_summary_text(response):
    parts = []
    for block in response.content:
        if getattr(block, "type", None) == "text":
            parts.append(block.text)
    return "\n".join(parts).strip()


def _validate_summary(text):
    if not text or not isinstance(text, str):
        raise ValueError("Empty or non-string summary text")
    return text


def _template_summary(stats):
    """Rule-based, numbers-driven fallback used whenever the real Claude call
    doesn't produce a usable summary - missing/placeholder key, bad key, network
    error, or a malformed response all land here, not just a missing key, so the
    summary card always says something concrete about this week's actual numbers
    instead of a flat "unavailable" message. FALLBACK_SUMMARY (the flat string)
    is only used if this function itself errors."""
    total = stats["total_visits"]
    parts = [f"{total} visit{'s' if total != 1 else ''} in the past week."]

    if total > 0:
        no_show_rate = stats["no_show_count"] / total
        if no_show_rate > 0.15:
            parts.append(f"No-shows were notable: {stats['no_show_count']} of {total} visits.")

        if stats["booked_count"] > stats["walkin_count"] * 2:
            parts.append("Most visits came from bookings rather than walk-ins.")
        elif stats["walkin_count"] > stats["booked_count"] * 2:
            parts.append("Most visits were walk-ins rather than bookings.")

    if stats["average_wait_minutes"] is not None:
        if stats["average_wait_minutes"] > 30:
            parts.append(f"Average wait was {stats['average_wait_minutes']} min, on the higher side.")
        elif stats["average_wait_minutes"] < 15:
            parts.append(f"Average wait stayed low at {stats['average_wait_minutes']} min.")

    if stats["visits_per_doctor"]:
        top_doc = max(stats["visits_per_doctor"], key=lambda d: d["count"])
        if top_doc["count"] > 0:
            parts.append(f"{top_doc['doctor_name']} saw the most patients ({top_doc['count']}).")

    return " ".join(parts)


def generate_weekly_summary(stats):
    try:
        client = get_client()
        response = client.messages.create(
            model=MODEL,
            max_tokens=300,
            messages=[{"role": "user", "content": _build_summary_prompt(stats)}],
        )
        raw_text = _extract_summary_text(response)
        return _validate_summary(raw_text)
    except Exception as e:
        logger.error(f"Weekly summary generation failed: {e}")
        try:
            return _template_summary(stats)
        except Exception as template_error:
            logger.error(f"Template summary fallback also failed: {template_error}")
            return FALLBACK_SUMMARY


def store_weekly_analytics(stats, summary):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO weekly_analytics (stats_json, summary_text, generated_at) VALUES (?, ?, ?)",
        (json.dumps(stats), summary, datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()
    conn.close()


def run_weekly_analytics_job():
    stats = compute_weekly_stats()
    summary = generate_weekly_summary(stats)
    store_weekly_analytics(stats, summary)
    logger.info(f"Weekly analytics updated: {stats['total_visits']} visits in window")
