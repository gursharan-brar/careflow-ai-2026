from flask import Blueprint, request, jsonify, session

from db import get_db, now_iso
from staff_chat import get_staff_reply
from auth import require_staff_login
from rate_limit import limiter

staff_chat_bp = Blueprint("staff_chat", __name__)

MAX_MESSAGE_LENGTH = 2000
MAX_HISTORY_LENGTH = 50


def _log_turn(staff_id, role, content):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO chat_log (chat_type, visit_id, staff_id, session_id, role, content, created_at)
        VALUES ('staff', NULL, ?, NULL, ?, ?, ?)
        """,
        (staff_id, role, content, now_iso()),
    )
    conn.commit()
    conn.close()


@staff_chat_bp.route("/api/chat/staff", methods=["POST"])
@require_staff_login
@limiter.limit("30 per minute")
def chat_staff():
    data = request.get_json(silent=True) or {}

    message = (data.get("message") or "").strip()
    history = data.get("history")
    staff_id = session.get("staff_id")

    if not message:
        return jsonify({"error": "message is required"}), 400

    if len(message) > MAX_MESSAGE_LENGTH:
        return jsonify({"error": f"message must be {MAX_MESSAGE_LENGTH} characters or fewer"}), 400

    if not isinstance(history, list):
        history = []

    if len(history) > MAX_HISTORY_LENGTH:
        return jsonify({"error": f"history must contain {MAX_HISTORY_LENGTH} turns or fewer"}), 400

    reply = get_staff_reply(message, history)

    _log_turn(staff_id, "user", message)
    _log_turn(staff_id, "assistant", reply)

    return jsonify({"reply": reply})
