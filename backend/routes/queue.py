from flask import Blueprint, jsonify

from db import get_db
from mail import send_position3_email

queue_bp = Blueprint("queue", __name__)

ACTIVE_EXCLUDE = ("completed", "no_show")


@queue_bp.route("/api/queue", methods=["GET"])
def get_queue():
    conn = get_db()
    cur = conn.cursor()
    placeholders = ",".join("?" for _ in ACTIVE_EXCLUDE)
    cur.execute(
        f"""
        SELECT id, name, visit_type, queue_position, priority_level, status,
               estimated_wait, health_alert_match, created_at, email, position3_notified
        FROM visits
        WHERE status NOT IN ({placeholders})
        ORDER BY queue_position ASC
        """,
        ACTIVE_EXCLUDE,
    )
    rows = cur.fetchall()

    result = []
    position3_candidates = []
    for row in rows:
        result.append({
            "visit_id": row["id"],
            "name": row["name"],
            "visit_type": row["visit_type"],
            "queue_position": row["queue_position"],
            "priority_level": row["priority_level"],
            "status": row["status"],
            "estimated_wait": row["estimated_wait"],
            "health_alert_match": row["health_alert_match"],
            "created_at": row["created_at"],
        })
        if row["queue_position"] == 3 and row["position3_notified"] == 0:
            position3_candidates.append((row["id"], row["name"], row["email"]))

    if position3_candidates:
        cur.executemany(
            "UPDATE visits SET position3_notified = 1 WHERE id = ?",
            [(vid,) for vid, _, _ in position3_candidates],
        )
        conn.commit()

    conn.close()

    for _, name, email in position3_candidates:
        send_position3_email(name, email)

    return jsonify(result)
