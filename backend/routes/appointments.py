import re
from datetime import datetime, date

from flask import Blueprint, request, jsonify

from db import get_db, get_db_for_transaction, now_iso, BOOKING_SLOTS, APPOINTMENT_ACTIVE_STATUSES_EXCLUDE
from auth import require_staff_login
from mail import send_booking_confirmation
from rate_limit import limiter

appointments_bp = Blueprint("appointments", __name__)

EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MAX_NAME_LENGTH = 100
MAX_EMAIL_LENGTH = 254
MAX_PHONE_LENGTH = 20
VALID_DATE_REGEX = re.compile(r"^\d{4}-\d{2}-\d{2}$")
VALID_APPOINTMENT_STATUSES = ("cancelled", "completed")


def _today_str():
    return date.today().isoformat()


def _is_valid_date_format(value):
    return bool(VALID_DATE_REGEX.match(value or ""))


def _get_doctor(cur, doctor_id):
    cur.execute("SELECT id, name, status FROM doctors WHERE id = ?", (doctor_id,))
    return cur.fetchone()


def _slot_has_passed(slot_time):
    """Whether a slot's start time is already behind the current server clock.
    Only meaningful when the slot's date is today — callers must check that
    separately."""
    now = datetime.now()
    slot_dt = datetime.strptime(slot_time, "%H:%M").replace(year=now.year, month=now.month, day=now.day)
    return slot_dt < now


@appointments_bp.route("/api/appointments/slots", methods=["GET"])
def get_slots():
    slot_date = (request.args.get("date") or "").strip()
    doctor_id_raw = (request.args.get("doctor_id") or "").strip()

    if not _is_valid_date_format(slot_date):
        return jsonify({"error": "date must be in YYYY-MM-DD format"}), 400

    if slot_date != _today_str():
        return jsonify({"error": "appointments can only be booked for today"}), 400

    if not doctor_id_raw.isdigit():
        return jsonify({"error": "doctor_id must be a valid integer"}), 400
    doctor_id = int(doctor_id_raw)

    conn = get_db()
    cur = conn.cursor()
    doctor = _get_doctor(cur, doctor_id)

    if not doctor:
        conn.close()
        return jsonify({"error": "doctor not found"}), 400

    placeholders = ",".join("?" for _ in APPOINTMENT_ACTIVE_STATUSES_EXCLUDE)
    cur.execute(
        f"""
        SELECT slot_time FROM appointments
        WHERE doctor_id = ? AND slot_date = ? AND status NOT IN ({placeholders})
        """,
        (doctor_id, slot_date, *APPOINTMENT_ACTIVE_STATUSES_EXCLUDE),
    )
    taken_slots = {row["slot_time"] for row in cur.fetchall()}
    conn.close()

    slots = [
        {
            "slot_time": slot_time,
            "available": slot_time not in taken_slots and not _slot_has_passed(slot_time),
        }
        for slot_time in BOOKING_SLOTS
    ]

    return jsonify(slots)


@appointments_bp.route("/api/appointments", methods=["POST"])
@limiter.limit("30 per minute")
def create_appointment():
    data = request.get_json(silent=True) or {}

    doctor_id = data.get("doctor_id")
    slot_time = (data.get("slot_time") or "").strip()
    slot_date = (data.get("slot_date") or "").strip()
    patient_name = (data.get("patient_name") or "").strip()
    patient_email = (data.get("patient_email") or "").strip()
    patient_phone = (data.get("patient_phone") or "").strip()

    if not isinstance(doctor_id, int):
        return jsonify({"error": "doctor_id must be an integer"}), 400

    if not _is_valid_date_format(slot_date) or slot_date != _today_str():
        return jsonify({"error": "slot_date must be today, in YYYY-MM-DD format"}), 400

    if slot_time not in BOOKING_SLOTS:
        return jsonify({"error": "slot_time must be one of the clinic's fixed 30-minute slots"}), 400

    if _slot_has_passed(slot_time):
        return jsonify({"error": "this slot has already passed today"}), 400

    if not patient_name:
        return jsonify({"error": "patient_name is required"}), 400

    if len(patient_name) > MAX_NAME_LENGTH:
        return jsonify({"error": f"patient_name must be {MAX_NAME_LENGTH} characters or fewer"}), 400

    if not patient_email or len(patient_email) > MAX_EMAIL_LENGTH or not EMAIL_REGEX.match(patient_email):
        return jsonify({"error": "a valid patient_email is required"}), 400

    if len(patient_phone) > MAX_PHONE_LENGTH:
        return jsonify({"error": f"patient_phone must be {MAX_PHONE_LENGTH} characters or fewer"}), 400

    conn = get_db_for_transaction()
    cur = conn.cursor()
    try:
        cur.execute("BEGIN IMMEDIATE")

        doctor = _get_doctor(cur, doctor_id)
        if not doctor:
            cur.execute("ROLLBACK")
            conn.close()
            return jsonify({"error": "doctor not found"}), 400

        if doctor["status"] != "on_shift":
            cur.execute("ROLLBACK")
            conn.close()
            return jsonify({"error": f"{doctor['name']} is not on shift today"}), 400

        placeholders = ",".join("?" for _ in APPOINTMENT_ACTIVE_STATUSES_EXCLUDE)
        cur.execute(
            f"""
            SELECT id FROM appointments
            WHERE doctor_id = ? AND slot_date = ? AND slot_time = ? AND status NOT IN ({placeholders})
            """,
            (doctor_id, slot_date, slot_time, *APPOINTMENT_ACTIVE_STATUSES_EXCLUDE),
        )
        if cur.fetchone():
            cur.execute("ROLLBACK")
            conn.close()
            return jsonify({"error": "This slot was just taken. Please choose another time."}), 409

        created_at = now_iso()
        cur.execute(
            """
            INSERT INTO appointments (doctor_id, patient_name, patient_email, patient_phone,
                                       slot_time, slot_date, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, 'confirmed', ?)
            """,
            (doctor_id, patient_name, patient_email, patient_phone or None, slot_time, slot_date, created_at),
        )
        appointment_id = cur.lastrowid
        cur.execute("COMMIT")
    except Exception:
        cur.execute("ROLLBACK")
        raise
    finally:
        conn.close()

    send_booking_confirmation(patient_name, patient_email, doctor["name"], slot_date, slot_time)

    return jsonify({
        "appointment_id": appointment_id,
        "doctor_name": doctor["name"],
        "slot_time": slot_time,
        "slot_date": slot_date,
        "patient_name": patient_name,
        "confirmation_message": f"Your appointment with {doctor['name']} at {slot_time} is confirmed.",
    }), 201


@appointments_bp.route("/api/appointments", methods=["GET"])
@require_staff_login
def list_appointments():
    slot_date = (request.args.get("date") or "").strip()

    if not _is_valid_date_format(slot_date):
        return jsonify({"error": "date must be in YYYY-MM-DD format"}), 400

    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT a.id, a.doctor_id, d.name AS doctor_name, a.patient_name, a.patient_email,
               a.patient_phone, a.slot_time, a.slot_date, a.status, a.visit_id
        FROM appointments a
        JOIN doctors d ON d.id = a.doctor_id
        WHERE a.slot_date = ? AND a.status = 'confirmed'
        ORDER BY a.slot_time ASC
        """,
        (slot_date,),
    )
    appointments = cur.fetchall()
    conn.close()

    return jsonify([
        {
            "id": a["id"],
            "doctor_id": a["doctor_id"],
            "doctor_name": a["doctor_name"],
            "patient_name": a["patient_name"],
            "patient_email": a["patient_email"],
            "patient_phone": a["patient_phone"],
            "slot_time": a["slot_time"],
            "slot_date": a["slot_date"],
            "status": a["status"],
            "visit_id": a["visit_id"],
        }
        for a in appointments
    ])


@appointments_bp.route("/api/appointments/<int:appointment_id>/status", methods=["PATCH"])
@require_staff_login
def update_appointment_status(appointment_id):
    data = request.get_json(silent=True) or {}
    new_status = (data.get("status") or "").strip()

    if new_status not in VALID_APPOINTMENT_STATUSES:
        return jsonify({"error": f"status must be one of {VALID_APPOINTMENT_STATUSES}"}), 400

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id FROM appointments WHERE id = ?", (appointment_id,))
    appointment = cur.fetchone()

    if not appointment:
        conn.close()
        return jsonify({"error": "appointment not found"}), 404

    cur.execute(
        "UPDATE appointments SET status = ? WHERE id = ?",
        (new_status, appointment_id),
    )
    conn.commit()
    conn.close()

    return jsonify({"id": appointment_id, "status": new_status})
