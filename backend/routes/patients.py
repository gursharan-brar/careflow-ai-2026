import json
import re
from datetime import datetime, timezone

from flask import Blueprint, request, jsonify, Response, session

from db import get_db, now_iso
from auth import require_staff_login

patients_bp = Blueprint("patients", __name__)

UUID4_REGEX = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$", re.IGNORECASE
)
DATE_REGEX = re.compile(r"^\d{4}-\d{2}-\d{2}$")

DEFAULT_PER_PAGE = 20
MAX_PER_PAGE = 50
MAX_SEARCH_LENGTH = 100

REAL_STATUSES = ("checked_in", "called", "in_progress", "completed", "no_show")
ACTIVE_STATUSES = ("checked_in", "called", "in_progress")
# "active" is a frontend convenience value, not a real visits.status value —
# it expands server-side to the same active/inactive split already used
# everywhere else in this codebase (see db.py's ACTIVE_STATUSES_EXCLUDE).
# "triaged" is deliberately NOT a valid value here: triage completion never
# changes visits.status (see checkin.py's /api/triage handler, which writes
# triage_summary but leaves status untouched), so it isn't a real state in
# VALID_TRANSITIONS (routes/visits.py) either. Filtering for triaged visits
# is covered by the list response's has_triage field instead, optionally
# combined with a real status value from this allowlist.
VALID_STATUS_FILTERS = ("all", "active") + REAL_STATUSES


def _is_valid_uuid4(value):
    return bool(UUID4_REGEX.match(value or ""))


def _parse_page_param(raw, default, minimum, maximum=None):
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return default, None
    if value < minimum:
        return None, f"must be an integer of at least {minimum}"
    if maximum is not None and value > maximum:
        return None, f"must be an integer no greater than {maximum}"
    return value, None


def _get_visit_detail(cur, visit_id):
    cur.execute(
        """
        SELECT v.id, v.name, v.email, v.phone, v.visit_type, v.queue_position, v.priority_level,
               v.triage_summary, v.flag_reason, v.triage_answers, v.status, v.estimated_wait,
               v.actual_wait, v.booked_slot_time, v.created_at, v.updated_at, d.name AS doctor_name
        FROM visits v
        LEFT JOIN doctors d ON v.doctor_id = d.id
        WHERE v.id = ?
        """,
        (visit_id,),
    )
    visit = cur.fetchone()
    if not visit:
        return None

    try:
        triage_answers = json.loads(visit["triage_answers"]) if visit["triage_answers"] else None
    except (ValueError, TypeError):
        triage_answers = None

    cur.execute(
        """
        SELECT event_type, old_status, new_status, actor, timestamp
        FROM audit_log
        WHERE visit_id = ?
        ORDER BY timestamp ASC
        """,
        (visit_id,),
    )
    audit_trail = [dict(row) for row in cur.fetchall()]

    cur.execute(
        """
        SELECT role, content, created_at
        FROM chat_log
        WHERE visit_id = ? AND chat_type = 'patient'
        ORDER BY created_at ASC
        """,
        (visit_id,),
    )
    chat_log = [dict(row) for row in cur.fetchall()]

    cur.execute(
        "SELECT slot_time, slot_date, status FROM appointments WHERE visit_id = ?",
        (visit_id,),
    )
    appointment_row = cur.fetchone()
    appointment = dict(appointment_row) if appointment_row else None

    return {
        "id": visit["id"],
        "name": visit["name"],
        "visit_type": visit["visit_type"],
        "email": visit["email"],
        "phone": visit["phone"],
        "queue_position": visit["queue_position"],
        "priority_level": visit["priority_level"],
        "triage_summary": visit["triage_summary"],
        "flag_reason": visit["flag_reason"],
        "triage_answers": triage_answers,
        "status": visit["status"],
        "estimated_wait": visit["estimated_wait"],
        "actual_wait": visit["actual_wait"],
        "doctor_name": visit["doctor_name"],
        "booked_slot_time": visit["booked_slot_time"],
        "created_at": visit["created_at"],
        "updated_at": visit["updated_at"],
        "audit_trail": audit_trail,
        "chat_log": chat_log,
        "appointment": appointment,
    }


@patients_bp.route("/api/patients", methods=["GET"])
@require_staff_login
def list_patients():
    page, page_error = _parse_page_param(request.args.get("page"), default=1, minimum=1)
    if page_error:
        return jsonify({"error": f"page {page_error}"}), 400

    per_page, per_page_error = _parse_page_param(
        request.args.get("per_page"), default=DEFAULT_PER_PAGE, minimum=1, maximum=MAX_PER_PAGE
    )
    if per_page_error:
        return jsonify({"error": f"per_page {per_page_error}"}), 400

    status = (request.args.get("status") or "all").strip()
    if status not in VALID_STATUS_FILTERS:
        return jsonify({"error": f"status must be one of {VALID_STATUS_FILTERS}"}), 400

    date_from = (request.args.get("date_from") or "").strip()
    if date_from and not DATE_REGEX.match(date_from):
        return jsonify({"error": "date_from must be in YYYY-MM-DD format"}), 400

    date_to = (request.args.get("date_to") or "").strip()
    if date_to and not DATE_REGEX.match(date_to):
        return jsonify({"error": "date_to must be in YYYY-MM-DD format"}), 400

    doctor_id_raw = (request.args.get("doctor_id") or "").strip()
    doctor_id = None
    if doctor_id_raw:
        if not doctor_id_raw.isdigit():
            return jsonify({"error": "doctor_id must be a valid integer"}), 400
        doctor_id = int(doctor_id_raw)

    search = None
    if "search" in request.args:
        raw_search = (request.args.get("search") or "")
        if len(raw_search) > MAX_SEARCH_LENGTH:
            return jsonify({"error": f"search must be {MAX_SEARCH_LENGTH} characters or fewer"}), 400
        stripped = raw_search.strip()
        if not stripped:
            return jsonify({"error": "search must not be empty"}), 400
        search = stripped

    where_clauses = []
    params = []

    if status == "active":
        placeholders = ",".join("?" for _ in ACTIVE_STATUSES)
        where_clauses.append(f"v.status IN ({placeholders})")
        params.extend(ACTIVE_STATUSES)
    elif status != "all":
        where_clauses.append("v.status = ?")
        params.append(status)

    if date_from:
        where_clauses.append("SUBSTR(v.created_at, 1, 10) >= ?")
        params.append(date_from)

    if date_to:
        where_clauses.append("SUBSTR(v.created_at, 1, 10) <= ?")
        params.append(date_to)

    if doctor_id is not None:
        where_clauses.append("v.doctor_id = ?")
        params.append(doctor_id)

    if search:
        where_clauses.append("v.name LIKE '%' || ? || '%'")
        params.append(search)

    where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

    conn = get_db()
    cur = conn.cursor()

    cur.execute(f"SELECT COUNT(*) AS count FROM visits v {where_sql}", params)
    total = cur.fetchone()["count"]
    pages = max(1, (total + per_page - 1) // per_page)
    offset = (page - 1) * per_page

    cur.execute(
        f"""
        SELECT v.id, v.name, v.visit_type, v.priority_level, v.status, v.estimated_wait,
               v.actual_wait, v.created_at, v.triage_summary,
               d.name AS doctor_name,
               EXISTS(SELECT 1 FROM chat_log c WHERE c.visit_id = v.id) AS has_chat
        FROM visits v
        LEFT JOIN doctors d ON v.doctor_id = d.id
        {where_sql}
        ORDER BY v.created_at DESC
        LIMIT ? OFFSET ?
        """,
        params + [per_page, offset],
    )
    rows = cur.fetchall()
    conn.close()

    visits = [
        {
            "id": row["id"],
            "name": row["name"],
            "visit_type": row["visit_type"],
            "priority_level": row["priority_level"],
            "status": row["status"],
            "doctor_name": row["doctor_name"],
            "estimated_wait": row["estimated_wait"],
            "actual_wait": row["actual_wait"],
            "created_at": row["created_at"],
            "has_triage": row["triage_summary"] is not None,
            "has_chat": bool(row["has_chat"]),
        }
        for row in rows
    ]

    return jsonify({
        "visits": visits,
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": pages,
    })


@patients_bp.route("/api/patients/<visit_id>", methods=["GET"])
@require_staff_login
def get_patient_detail(visit_id):
    if not _is_valid_uuid4(visit_id):
        return jsonify({"error": "visit_id must be a valid UUID"}), 400

    conn = get_db()
    cur = conn.cursor()
    detail = _get_visit_detail(cur, visit_id)
    conn.close()

    if not detail:
        return jsonify({"error": "visit not found"}), 404

    return jsonify(detail)


@patients_bp.route("/api/patients/export/<visit_id>", methods=["GET"])
@require_staff_login
def export_patient(visit_id):
    if not _is_valid_uuid4(visit_id):
        return jsonify({"error": "visit_id must be a valid UUID"}), 400

    conn = get_db()
    cur = conn.cursor()
    detail = _get_visit_detail(cur, visit_id)

    if not detail:
        conn.close()
        return jsonify({"error": "visit not found"}), 404

    # Exporting a patient record is a data-access event worth auditing, same
    # as a status change — doesn't touch visits.status itself, so old/new are
    # both the visit's current status, matching how triage_completed already
    # records a no-op status transition in checkin.py.
    actor = session.get("staff_name") or "unknown staff"
    cur.execute(
        """
        INSERT INTO audit_log (visit_id, patient_name, event_type, old_status, new_status, timestamp, actor)
        VALUES (?, ?, 'record_exported', ?, ?, ?, ?)
        """,
        (visit_id, detail["name"], detail["status"], detail["status"], now_iso(), actor),
    )
    conn.commit()
    conn.close()

    lines = []
    lines.append("CareFlow AI — Visit Summary")
    lines.append(f"Generated: {datetime.now(timezone.utc).isoformat()}")
    lines.append("---")
    lines.append(f"Patient: {detail['name']}")
    lines.append(f"Visit Type: {detail['visit_type']}")
    lines.append(f"Check-in: {detail['created_at']}")
    lines.append(f"Status: {detail['status']}")
    lines.append(f"Priority: {detail['priority_level'] or 'Not yet triaged'}")
    lines.append(f"Doctor: {detail['doctor_name'] or 'Unassigned'}")
    lines.append(f"Estimated Wait: {detail['estimated_wait']} min" if detail["estimated_wait"] is not None else "Estimated Wait: N/A")
    lines.append(f"Actual Wait: {detail['actual_wait']} min" if detail["actual_wait"] is not None else "Actual Wait: N/A")
    lines.append("")
    lines.append("TRIAGE SUMMARY")
    lines.append(detail["triage_summary"] or "Not yet triaged")
    lines.append("")
    lines.append("AI FLAG REASON")
    lines.append(detail["flag_reason"] or "None")
    lines.append("")
    lines.append("TRIAGE ANSWERS")
    if detail["triage_answers"]:
        for qa in detail["triage_answers"]:
            lines.append(f"Q: {qa.get('question', '')}")
            lines.append(f"A: {qa.get('answer', '')}")
    else:
        lines.append("Not recorded")
    lines.append("")
    lines.append("VISIT AUDIT TRAIL")
    if detail["audit_trail"]:
        for entry in detail["audit_trail"]:
            lines.append(
                f"{entry['timestamp']} — {entry['event_type']}: "
                f"{entry['old_status']} → {entry['new_status']} (actor: {entry['actor']})"
            )
    else:
        lines.append("No audit events recorded.")
    lines.append("")
    lines.append("CHAT LOG")
    if detail["chat_log"]:
        for turn in detail["chat_log"]:
            lines.append(f"[{turn['role']}] {turn['content']}")
    else:
        lines.append("No chat history")
    lines.append("")
    lines.append("APPOINTMENT")
    if detail["appointment"]:
        lines.append(f"Slot: {detail['appointment']['slot_date']} {detail['appointment']['slot_time']}")
        lines.append(f"Status: {detail['appointment']['status']}")
    else:
        lines.append("Walk-in visit — no prior appointment")
    lines.append("---")

    body = "\n".join(lines)
    filename = f"visit-{visit_id[:8]}.txt"

    return Response(
        body,
        mimetype="text/plain",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
