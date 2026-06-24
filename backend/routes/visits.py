from datetime import datetime
from flask import Blueprint, request, jsonify, session

from db import get_db, now_iso, ACTIVE_STATUSES_EXCLUDE, calculate_doctor_wait, get_doctor_position
from auth import require_staff_login

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
@require_staff_login
def update_status(visit_id):
    data = request.get_json(silent=True) or {}
    new_status = (data.get("status") or "").strip()
    actor = session.get("staff_name") or "unknown staff"

    if not new_status:
        return jsonify({"error": "status is required"}), 400

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


@visits_bp.route("/api/visits/<visit_id>/assign", methods=["PATCH"])
@require_staff_login
def assign_visit(visit_id):
    data = request.get_json(silent=True) or {}

    if "doctor_id" not in data:
        return jsonify({"error": "doctor_id is required (use null to unassign)"}), 400

    doctor_id = data.get("doctor_id")

    if doctor_id is not None and not isinstance(doctor_id, int):
        return jsonify({"error": "doctor_id must be an integer or null"}), 400

    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, visit_type, status, queue_position FROM visits WHERE id = ?",
        (visit_id,),
    )
    visit = cur.fetchone()

    if not visit:
        conn.close()
        return jsonify({"error": "visit not found"}), 404

    if doctor_id is not None:
        cur.execute("SELECT id, name, status FROM doctors WHERE id = ?", (doctor_id,))
        doctor = cur.fetchone()

        if not doctor:
            conn.close()
            return jsonify({"error": "doctor not found"}), 404

        if doctor["status"] != "on_shift":
            conn.close()
            return jsonify({"error": f"{doctor['name']} is not currently on shift"}), 400

    updated_at = now_iso()
    cur.execute(
        "UPDATE visits SET doctor_id = ?, updated_at = ? WHERE id = ?",
        (doctor_id, updated_at, visit_id),
    )

    if doctor_id is None:
        estimated_wait = None
        doctor_position = None
    else:
        doctor_position = get_doctor_position(cur, doctor_id, visit["queue_position"])
        estimated_wait = calculate_doctor_wait(visit["visit_type"], doctor_position)

    conn.commit()
    conn.close()

    return jsonify({
        "visit_id": visit_id,
        "doctor_id": doctor_id,
        "doctor_position": doctor_position,
        "estimated_wait": estimated_wait,
        "updated_at": updated_at,
    })
