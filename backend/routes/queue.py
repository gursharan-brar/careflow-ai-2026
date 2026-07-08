from flask import Blueprint, jsonify

from db import get_db, calculate_doctor_wait
from mail import send_position3_email
from auth import require_staff_login

queue_bp = Blueprint("queue", __name__)

ACTIVE_EXCLUDE = ("completed", "no_show")


def _mark_position3_notified(visit_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("UPDATE visits SET position3_notified = 1 WHERE id = ?", (visit_id,))
    conn.commit()
    conn.close()


@queue_bp.route("/api/queue", methods=["GET"])
@require_staff_login
def get_queue():
    conn = get_db()
    cur = conn.cursor()
    placeholders = ",".join("?" for _ in ACTIVE_EXCLUDE)
    cur.execute(
        f"""
        SELECT v.id, v.name, v.visit_type, v.queue_position, v.priority_level, v.status,
               v.health_alert_match, v.created_at, v.email, v.position3_notified, v.doctor_id,
               v.booked_slot_time, d.name AS doctor_name
        FROM visits v
        LEFT JOIN doctors d ON v.doctor_id = d.id
        WHERE v.status NOT IN ({placeholders})
        ORDER BY (v.booked_slot_time IS NULL) ASC, v.booked_slot_time ASC, v.queue_position ASC
        """,
        ACTIVE_EXCLUDE,
    )
    rows = cur.fetchall()

    result = []
    position3_candidates = []
    # Rows already arrive ordered by global queue_position, so a running
    # per-doctor counter reproduces "count of this doctor's active patients
    # with a lower queue_position, plus one" without an extra query per row.
    doctor_position_counters = {}
    for row in rows:
        doctor_id = row["doctor_id"]
        if doctor_id is None:
            doctor_position = None
            estimated_wait = None
        else:
            doctor_position_counters[doctor_id] = doctor_position_counters.get(doctor_id, 0) + 1
            doctor_position = doctor_position_counters[doctor_id]
            estimated_wait = calculate_doctor_wait(row["visit_type"], doctor_position)

        result.append({
            "visit_id": row["id"],
            "name": row["name"],
            "visit_type": row["visit_type"],
            "queue_position": row["queue_position"],
            "priority_level": row["priority_level"],
            "status": row["status"],
            "estimated_wait": estimated_wait,
            "health_alert_match": row["health_alert_match"],
            "created_at": row["created_at"],
            "doctor_id": doctor_id,
            "doctor_name": row["doctor_name"],
            "doctor_position": doctor_position,
            "booked_slot_time": row["booked_slot_time"],
        })
        if row["queue_position"] == 3 and row["position3_notified"] == 0:
            position3_candidates.append((row["id"], row["name"], row["email"]))

    conn.close()

    for visit_id, name, email in position3_candidates:
        send_position3_email(name, email, on_success=lambda vid=visit_id: _mark_position3_notified(vid))

    return jsonify(result)
