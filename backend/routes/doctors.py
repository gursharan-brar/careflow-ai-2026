from flask import Blueprint, request, jsonify

from db import get_db, now_iso, ACTIVE_STATUSES_EXCLUDE
from auth import require_staff_login

doctors_bp = Blueprint("doctors", __name__)

MAX_NAME_LENGTH = 100
VALID_STATUSES = ("on_shift", "off_shift", "inactive")


def _active_patient_counts(cur):
    placeholders = ",".join("?" for _ in ACTIVE_STATUSES_EXCLUDE)
    cur.execute(
        f"""
        SELECT doctor_id, COUNT(*) AS count FROM visits
        WHERE status NOT IN ({placeholders}) AND doctor_id IS NOT NULL
        GROUP BY doctor_id
        """,
        ACTIVE_STATUSES_EXCLUDE,
    )
    return {row["doctor_id"]: row["count"] for row in cur.fetchall()}


def _active_count_for_doctor(cur, doctor_id):
    placeholders = ",".join("?" for _ in ACTIVE_STATUSES_EXCLUDE)
    cur.execute(
        f"SELECT COUNT(*) AS count FROM visits WHERE doctor_id = ? AND status NOT IN ({placeholders})",
        (doctor_id, *ACTIVE_STATUSES_EXCLUDE),
    )
    return cur.fetchone()["count"]


@doctors_bp.route("/api/doctors", methods=["GET"])
@require_staff_login
def get_doctors():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id, name, status FROM doctors WHERE status != 'inactive' ORDER BY id")
    doctors = cur.fetchall()
    counts = _active_patient_counts(cur)
    conn.close()

    return jsonify([
        {
            "id": d["id"],
            "name": d["name"],
            "status": d["status"],
            "active_patient_count": counts.get(d["id"], 0),
        }
        for d in doctors
    ])


@doctors_bp.route("/api/doctors/public", methods=["GET"])
def get_doctors_public():
    """Unauthenticated, patient-facing doctor listing for the booking page.
    Returns id/name/status only — no active_patient_count or other
    operational data that isn't appropriate to expose publicly."""
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id, name, status FROM doctors WHERE status != 'inactive' ORDER BY id")
    doctors = cur.fetchall()
    conn.close()

    return jsonify([
        {"id": d["id"], "name": d["name"], "status": d["status"]}
        for d in doctors
    ])


@doctors_bp.route("/api/doctors/on-shift", methods=["GET"])
@require_staff_login
def get_on_shift_doctors():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id, name FROM doctors WHERE status = 'on_shift' ORDER BY id")
    doctors = cur.fetchall()
    counts = _active_patient_counts(cur)
    conn.close()

    return jsonify([
        {
            "id": d["id"],
            "name": d["name"],
            "active_patient_count": counts.get(d["id"], 0),
        }
        for d in doctors
    ])


@doctors_bp.route("/api/doctors", methods=["POST"])
@require_staff_login
def create_doctor():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()

    if not name:
        return jsonify({"error": "name is required"}), 400

    if len(name) > MAX_NAME_LENGTH:
        return jsonify({"error": f"name must be {MAX_NAME_LENGTH} characters or fewer"}), 400

    conn = get_db()
    cur = conn.cursor()
    cur.execute("INSERT INTO doctors (name, status) VALUES (?, 'off_shift')", (name,))
    new_id = cur.lastrowid
    conn.commit()
    conn.close()

    return jsonify({"id": new_id, "name": name, "status": "off_shift", "active_patient_count": 0}), 201


@doctors_bp.route("/api/doctors/<int:doctor_id>/status", methods=["PATCH"])
@require_staff_login
def update_doctor_status(doctor_id):
    data = request.get_json(silent=True) or {}
    new_status = (data.get("status") or "").strip()

    if new_status not in VALID_STATUSES:
        return jsonify({"error": f"status must be one of {VALID_STATUSES}"}), 400

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id, name FROM doctors WHERE id = ?", (doctor_id,))
    doctor = cur.fetchone()

    if not doctor:
        conn.close()
        return jsonify({"error": "doctor not found"}), 404

    active_count = _active_count_for_doctor(cur, doctor_id)

    if new_status == "inactive" and active_count > 0:
        conn.close()
        return jsonify({
            "error": (
                f"Cannot mark {doctor['name']} inactive — they have {active_count} active "
                "patient(s) assigned. Reassign them first."
            )
        }), 400

    cur.execute(
        "UPDATE doctors SET status = ?, updated_at = ? WHERE id = ?",
        (new_status, now_iso(), doctor_id),
    )
    conn.commit()
    conn.close()

    response = {
        "doctor": {
            "id": doctor_id,
            "name": doctor["name"],
            "status": new_status,
            "active_patient_count": active_count,
        }
    }

    # Marking someone off shift mid-shift is a legitimate real-world action (they
    # had to leave early) — allow it, but surface a warning so the receptionist
    # knows those patients won't move on their own.
    if new_status == "off_shift" and active_count > 0:
        response["warning"] = (
            f"{doctor['name']} has {active_count} active patient(s) still assigned. "
            "They will remain in their lane until manually reassigned."
        )

    return jsonify(response)
