import json
from flask import Blueprint, jsonify

from db import get_db
from auth import require_staff_login

health_bp = Blueprint("health", __name__)


@health_bp.route("/api/health-feed", methods=["GET"])
@require_staff_login
def get_health_feed():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT entries, fetched_at FROM health_feed ORDER BY id DESC LIMIT 1")
    row = cur.fetchone()
    conn.close()

    if not row:
        return jsonify({"entries": [], "fetched_at": None})

    return jsonify({"entries": json.loads(row["entries"]), "fetched_at": row["fetched_at"]})
