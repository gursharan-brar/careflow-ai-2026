from flask import Blueprint, request, jsonify, session
from werkzeug.security import check_password_hash

from db import get_db
from rate_limit import limiter

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/api/login", methods=["POST"])
@limiter.limit("5 per minute")
def login():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""

    if not username or not password:
        return jsonify({"error": "invalid credentials"}), 401

    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, password_hash, display_name FROM staff_users WHERE username = ?",
        (username,),
    )
    staff = cur.fetchone()
    conn.close()

    if not staff or not check_password_hash(staff["password_hash"], password):
        return jsonify({"error": "invalid credentials"}), 401

    session["staff_id"] = staff["id"]
    session["staff_name"] = staff["display_name"]

    return jsonify({"display_name": staff["display_name"]})


@auth_bp.route("/api/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"status": "ok"})


@auth_bp.route("/api/session", methods=["GET"])
def get_session():
    if not session.get("staff_id"):
        return jsonify({"authenticated": False})

    return jsonify({"authenticated": True, "display_name": session.get("staff_name")})
