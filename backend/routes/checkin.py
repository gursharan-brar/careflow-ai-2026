import re
from flask import Blueprint, request, jsonify

from db import get_db, get_db_for_transaction, generate_id, calculate_wait, get_next_queue_position, now_iso
from mail import send_welcome_email
from triage import classify_triage
from rate_limit import limiter

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

    if not name or not visit_type or not email or not phone:
        return jsonify({"error": "name, visit_type, email, and phone are required"}), 400

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

    visit_id = generate_id()
    created_at = now_iso()

    conn = get_db_for_transaction()
    cur = conn.cursor()
    try:
        cur.execute("BEGIN IMMEDIATE")
        queue_position = get_next_queue_position(cur)
        estimated_wait = calculate_wait(visit_type, queue_position)
        cur.execute(
            """
            INSERT INTO visits (id, name, visit_type, email, phone, queue_position,
                                 status, estimated_wait, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, 'checked_in', ?, ?, ?)
            """,
            (visit_id, name, visit_type, email, phone, queue_position, estimated_wait, created_at, created_at),
        )
        cur.execute("COMMIT")
    except Exception:
        cur.execute("ROLLBACK")
        raise
    finally:
        conn.close()

    send_welcome_email(name, visit_type, queue_position, estimated_wait, email)

    return jsonify({
        "visit_id": visit_id,
        "queue_position": queue_position,
        "estimated_wait": estimated_wait,
        "status": "checked_in",
    }), 201


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
