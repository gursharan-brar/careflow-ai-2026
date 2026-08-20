import json
import re
from datetime import date
from flask import Blueprint, request, jsonify

from db import (
    get_db,
    get_db_for_transaction,
    generate_id,
    calculate_wait,
    get_next_queue_position,
    now_iso,
    ACTIVE_STATUSES_EXCLUDE,
    HEALTH_ID_REGEX,
)
from mail import send_welcome_email
from triage import classify_triage, TRIAGE_QUESTIONS
from rate_limit import limiter
from routes.appointments import get_doctor, convert_appointment_to_visit, slot_has_passed

checkin_bp = Blueprint("checkin", __name__)

VALID_VISIT_TYPES = ("gp_consult", "prescription_renewal", "injury", "general")
EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

MAX_NAME_LENGTH = 100
MAX_EMAIL_LENGTH = 254
MAX_PHONE_LENGTH = 20


@checkin_bp.route("/api/checkin", methods=["POST"])
@limiter.limit("30 per minute")
def checkin():
    data = request.get_json(silent=True) or {}

    name = (data.get("name") or "").strip()
    visit_type = (data.get("visit_type") or "").strip()
    email = (data.get("email") or "").strip()
    phone = (data.get("phone") or "").strip()
    health_id = (data.get("health_id") or "").strip()

    if not name or not visit_type or not email or not phone or not health_id:
        return jsonify({"error": "name, visit_type, email, phone, and health_id are required"}), 400

    if len(name) > MAX_NAME_LENGTH:
        return jsonify({"error": f"name must be {MAX_NAME_LENGTH} characters or fewer"}), 400

    if len(email) > MAX_EMAIL_LENGTH:
        return jsonify({"error": f"email must be {MAX_EMAIL_LENGTH} characters or fewer"}), 400

    if len(phone) > MAX_PHONE_LENGTH:
        return jsonify({"error": f"phone must be {MAX_PHONE_LENGTH} characters or fewer"}), 400

    if visit_type not in VALID_VISIT_TYPES:
        return jsonify({"error": f"visit_type must be one of {VALID_VISIT_TYPES}"}), 400

    if not EMAIL_REGEX.match(email):
        return jsonify({"error": "invalid email format"}), 400

    if not HEALTH_ID_REGEX.match(health_id):
        return jsonify({
            "error": (
                "health_id must be exactly 9 digits, numeric only, with no dashes or letters. "
                "This checks format only - it does not verify that the PHN is registered or active."
            )
        }), 400

    conn = get_db_for_transaction()
    cur = conn.cursor()
    matched_appointment = None
    assign_doctor = True
    stale_slot_value = None
    try:
        cur.execute("BEGIN IMMEDIATE")

        placeholders = ",".join("?" for _ in ACTIVE_STATUSES_EXCLUDE)
        cur.execute(
            f"SELECT id FROM visits WHERE health_id = ? AND status NOT IN ({placeholders})",
            (health_id, *ACTIVE_STATUSES_EXCLUDE),
        )
        if cur.fetchone():
            cur.execute("ROLLBACK")
            conn.close()
            return jsonify({"error": "This health ID already has an active visit in the queue."}), 409

        # A confirmed same-day appointment for this PHN means the patient is
        # walking in for a booking they already made, not a fresh visit - merge
        # into it via the same conversion Arrived uses, rather than creating a
        # second, disconnected visit for the same person (see routes/appointments.py).
        today_str = date.today().isoformat()
        cur.execute(
            "SELECT id, doctor_id, patient_name, patient_email, patient_phone, health_id, slot_time, status, visit_id "
            "FROM appointments WHERE health_id = ? AND status = 'confirmed' AND slot_date = ?",
            (health_id, today_str),
        )
        matched_appointment = cur.fetchone()

        if matched_appointment:
            doctor = get_doctor(cur, matched_appointment["doctor_id"])
            assign_doctor = doctor is not None and doctor["status"] == "on_shift"
            stale_slot_value = (
                matched_appointment["slot_time"]
                if slot_has_passed(matched_appointment["slot_time"])
                else None
            )

            visit_id, queue_position, estimated_wait, doctor_id = convert_appointment_to_visit(
                cur,
                matched_appointment,
                "system (check-in merge)",
                visit_type=visit_type,
                patient_name=name,
                patient_email=email,
                patient_phone=phone,
                assign_doctor=assign_doctor,
                stale_slot_at_checkin=stale_slot_value,
            )
        else:
            visit_id = generate_id()
            created_at = now_iso()
            queue_position = get_next_queue_position(cur)
            estimated_wait = calculate_wait(visit_type, queue_position)
            cur.execute(
                """
                INSERT INTO visits (id, name, visit_type, email, phone, health_id, queue_position,
                                     status, estimated_wait, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'checked_in', ?, ?, ?)
                """,
                (
                    visit_id, name, visit_type, email, phone, health_id,
                    queue_position, estimated_wait, created_at, created_at,
                ),
            )

        cur.execute("COMMIT")
    except Exception:
        cur.execute("ROLLBACK")
        raise
    finally:
        conn.close()

    send_welcome_email(name, visit_type, queue_position, estimated_wait, email)

    response = {
        "visit_id": visit_id,
        "queue_position": queue_position,
        "estimated_wait": estimated_wait,
        "status": "checked_in",
    }

    if matched_appointment:
        response["merged_appointment_id"] = matched_appointment["id"]
        if not assign_doctor:
            response["doctor_off_shift"] = True
            response["note"] = (
                "Your originally booked doctor is currently off shift. "
                "A staff member will assign you to an available doctor."
            )
        if stale_slot_value:
            response["stale_appointment_slot"] = stale_slot_value

    return jsonify(response), 201


@checkin_bp.route("/api/triage", methods=["POST"])
@limiter.limit("30 per minute")
def triage():
    data = request.get_json(silent=True) or {}

    visit_id = (data.get("visit_id") or "").strip()
    symptom_answers = data.get("symptom_answers")

    if not visit_id:
        return jsonify({"error": "visit_id is required"}), 400

    if not isinstance(symptom_answers, list) or len(symptom_answers) != 5 or \
            not all(isinstance(a, str) for a in symptom_answers):
        return jsonify({"error": "symptom_answers must be an array of exactly 5 strings"}), 400

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id, name, visit_type, status, triage_summary FROM visits WHERE id = ?", (visit_id,))
    visit = cur.fetchone()

    if not visit:
        conn.close()
        return jsonify({"error": "visit not found"}), 404

    if visit["triage_summary"]:
        conn.close()
        return jsonify({"error": "triage has already been submitted for this visit"}), 409

    # Persisted before the Claude call so the patient's raw answers are never
    # lost if classify_triage() raises (network error, bad response, etc).
    questions = TRIAGE_QUESTIONS.get(visit["visit_type"], TRIAGE_QUESTIONS["general"])
    triage_answers = json.dumps([
        {"question": questions[i], "answer": symptom_answers[i]}
        for i in range(min(len(questions), len(symptom_answers)))
    ])
    cur.execute(
        "UPDATE visits SET triage_answers = ?, updated_at = ? WHERE id = ?",
        (triage_answers, now_iso(), visit_id),
    )
    conn.commit()

    result = classify_triage(visit["visit_type"], symptom_answers)
    updated_at = now_iso()

    cur.execute(
        "UPDATE visits SET priority_level = ?, triage_summary = ?, flag_reason = ?, updated_at = ? WHERE id = ?",
        (result["priority_level"], result["summary"], result["flag_reason"], updated_at, visit_id),
    )

    cur.execute(
        """
        INSERT INTO audit_log (visit_id, patient_name, event_type, old_status, new_status, timestamp, actor)
        VALUES (?, ?, 'triage_completed', ?, ?, ?, 'system')
        """,
        (visit_id, visit["name"], visit["status"], visit["status"], updated_at),
    )

    conn.commit()
    conn.close()

    return jsonify({
        "visit_id": visit_id,
        "priority_level": result["priority_level"],
        "summary": result["summary"],
        "flag_reason": result["flag_reason"],
    })
