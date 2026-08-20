from datetime import datetime, timedelta, date

from flask import Blueprint, jsonify

from db import get_db, calculate_doctor_wait
from mail import send_position3_email
from auth import require_staff_login

queue_bp = Blueprint("queue", __name__)

ACTIVE_EXCLUDE = ("completed", "no_show")

# How far ahead of now a confirmed appointment must start to surface the
# staff-facing "heads up" banner on that doctor's queue lane.
UPCOMING_APPOINTMENT_WINDOW_MINUTES = 45


def _mark_position3_notified(visit_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("UPDATE visits SET position3_notified = 1 WHERE id = ?", (visit_id,))
    conn.commit()
    conn.close()


def _format_slot_time(slot_time):
    """"HH:MM" (24-hour, as stored in appointments.slot_time) -> "H:MM AM/PM"."""
    hour, minute = (int(part) for part in slot_time.split(":"))
    period = "PM" if hour >= 12 else "AM"
    hour12 = hour % 12 or 12
    return f"{hour12}:{minute:02d} {period}"


def _get_upcoming_appointment(cur, doctor_id, now, today_str):
    """Earliest confirmed appointment for this doctor today that starts within
    UPCOMING_APPOINTMENT_WINDOW_MINUTES of now, or None. Mirrors the naive
    server-local time handling _slot_has_passed() already uses in
    routes/appointments.py — slot_time carries no timezone of its own."""
    cur.execute(
        """
        SELECT slot_time FROM appointments
        WHERE doctor_id = ? AND status = 'confirmed' AND slot_date = ?
        ORDER BY slot_time ASC
        """,
        (doctor_id, today_str),
    )
    window_end = now + timedelta(minutes=UPCOMING_APPOINTMENT_WINDOW_MINUTES)
    for row in cur.fetchall():
        slot_dt = datetime.strptime(row["slot_time"], "%H:%M").replace(
            year=now.year, month=now.month, day=now.day
        )
        if slot_dt < now:
            continue
        if slot_dt > window_end:
            break
        return {
            "slot_time": _format_slot_time(row["slot_time"]),
            "minutes_away": int((slot_dt - now).total_seconds() // 60),
        }
    return None


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
               v.booked_slot_time, v.needs_doctor_reassignment, v.stale_slot_at_checkin, d.name AS doctor_name
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
    now = datetime.now()
    today_str = date.today().isoformat()
    upcoming_appointment_cache = {}
    for row in rows:
        doctor_id = row["doctor_id"]
        if doctor_id is None:
            doctor_position = None
            estimated_wait = None
            upcoming_appointment = None
        else:
            doctor_position_counters[doctor_id] = doctor_position_counters.get(doctor_id, 0) + 1
            doctor_position = doctor_position_counters[doctor_id]
            estimated_wait = calculate_doctor_wait(row["visit_type"], doctor_position)
            if doctor_id not in upcoming_appointment_cache:
                upcoming_appointment_cache[doctor_id] = _get_upcoming_appointment(cur, doctor_id, now, today_str)
            upcoming_appointment = upcoming_appointment_cache[doctor_id]

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
            "needs_doctor_reassignment": bool(row["needs_doctor_reassignment"]),
            "stale_slot_at_checkin": row["stale_slot_at_checkin"],
            "upcoming_appointment": upcoming_appointment,
        })
        if row["queue_position"] == 3 and row["position3_notified"] == 0:
            position3_candidates.append((row["id"], row["name"], row["email"]))

    conn.close()

    for visit_id, name, email in position3_candidates:
        send_position3_email(name, email, on_success=lambda vid=visit_id: _mark_position3_notified(vid))

    return jsonify(result)
