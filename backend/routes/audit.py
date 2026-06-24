from flask import Blueprint, jsonify

from db import get_db
from auth import require_staff_login

audit_bp = Blueprint("audit", __name__)


@audit_bp.route("/api/audit", methods=["GET"])
@require_staff_login
def get_audit():
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, visit_id, patient_name, event_type, old_status, new_status, timestamp, actor
        FROM audit_log
        ORDER BY timestamp DESC
        LIMIT 200
        """
    )
    rows = cur.fetchall()
    conn.close()

    return jsonify([dict(row) for row in rows])
