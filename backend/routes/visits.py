from datetime import datetime
from flask import Blueprint, request, jsonify

from db import get_db, now_iso, ACTIVE_STATUSES_EXCLUDE

visits_bp = Blueprint("visits", __name__)

VALID_TRANSITIONS = {
    "checked_in": ("called", "no_show"),
    "called": ("in_progress", "no_show"),
    "in_progress": ("completed", "no_show"),
    "completed": (),
    "no_show": (),
}


@visits_bp.route("/api/visit/<visit_id>", methods=["GET"])
def get_visit(visit_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, name, visit_type, status, queue_position, estimated_wait, priority_level
        FROM visits WHERE id = ?
        """,
        (visit_id,),
    )
    visit = cur.fetchone()

    if not visit:
        conn.close()
        return jsonify({"error": "visit not found"}), 404

    people_ahead = 0
    if visit["status"] not in ACTIVE_STATUSES_EXCLUDE:
        placeholders = ",".join("?" for _ in ACTIVE_STATUSES_EXCLUDE)
        cur.execute(
            f"""
            SELECT COUNT(*) AS count FROM visits
            WHERE status NOT IN ({placeholders}) AND queue_position < ?
            """,
            ACTIVE_STATUSES_EXCLUDE + (visit["queue_position"],),
        )
        people_ahead = cur.fetchone()["count"]

    conn.close()

    return jsonify({
        "visit_id": visit["id"],
        "name": visit["name"],
        "visit_type": visit["visit_type"],
        "status": visit["status"],
        "queue_position": visit["queue_position"],
        "people_ahead": people_ahead,
        "estimated_wait": visit["estimated_wait"],
        "priority_level": visit["priority_level"],
    })


@visits_bp.route("/api/visit/<visit_id>/status", methods=["PATCH"])
def update_status(visit_id):
    data = request.get_json(silent=True) or {}
    new_status = (data.get("status") or "").strip()
    actor = (data.get("actor") or "").strip()

    if not new_status or not actor:
        return jsonify({"error": "status and actor are required"}), 400

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id, name, status, created_at FROM visits WHERE id = ?", (visit_id,))
    visit = cur.fetchone()

    if not visit:
        conn.close()
        return jsonify({"error": "visit not found"}), 404

    old_status = visit["status"]
    allowed = VALID_TRANSITIONS.get(old_status, ())

    if new_status not in allowed:
        conn.close()
        return jsonify({"error": f"cannot transition from {old_status} to {new_status}"}), 400

    updated_at = now_iso()

    if new_status == "completed":
        created = datetime.fromisoformat(visit["created_at"])
        now = datetime.fromisoformat(updated_at)
        actual_wait = int((now - created).total_seconds() // 60)
        cur.execute(
            "UPDATE visits SET status = ?, updated_at = ?, actual_wait = ? WHERE id = ?",
            (new_status, updated_at, actual_wait, visit_id),
        )
    else:
        cur.execute(
            "UPDATE visits SET status = ?, updated_at = ? WHERE id = ?",
            (new_status, updated_at, visit_id),
        )

    cur.execute(
        """
        INSERT INTO audit_log (visit_id, patient_name, event_type, old_status, new_status, timestamp, actor)
        VALUES (?, ?, 'status_change', ?, ?, ?, ?)
        """,
        (visit_id, visit["name"], old_status, new_status, updated_at, actor),
    )

    conn.commit()
    conn.close()

    return jsonify({
        "visit_id": visit_id,
        "status": new_status,
        "updated_at": updated_at,
    })
