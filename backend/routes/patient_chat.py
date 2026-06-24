import json

from flask import Blueprint, request, jsonify

from db import get_db, now_iso
from patient_chat import get_patient_reply, DISCLAIMER
from rate_limit import limiter

patient_chat_bp = Blueprint("patient_chat", __name__)

MAX_MESSAGE_LENGTH = 2000
MAX_HISTORY_LENGTH = 50


def _log_turn(visit_id, session_id, role, content):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO chat_log (chat_type, visit_id, staff_id, session_id, role, content, created_at)
        VALUES ('patient', ?, NULL, ?, ?, ?, ?)
        """,
        (visit_id, session_id, role, content, now_iso()),
    )
    conn.commit()
    conn.close()


@patient_chat_bp.route("/api/chat/patient", methods=["POST"])
@limiter.limit("30 per minute")
def chat_patient():
    data = request.get_json(silent=True) or {}

    message = (data.get("message") or "").strip()
    history = data.get("history")
    visit_id = (data.get("visit_id") or "").strip() or None
    session_id = (data.get("session_id") or "").strip() or None

    if not message:
        return jsonify({"error": "message is required"}), 400

    if len(message) > MAX_MESSAGE_LENGTH:
        return jsonify({"error": f"message must be {MAX_MESSAGE_LENGTH} characters or fewer"}), 400

    if not isinstance(history, list):
        history = []

    if len(history) > MAX_HISTORY_LENGTH:
        return jsonify({"error": f"history must contain {MAX_HISTORY_LENGTH} turns or fewer"}), 400

    reply, tool_call_info = get_patient_reply(message, history, visit_id)

    # Applied once here, regardless of which branch in get_patient_reply produced
    # the reply, so every patient-facing message carries it without exception.
    reply_with_disclaimer = f"{reply}\n\n{DISCLAIMER}"

    _log_turn(visit_id, session_id, "user", message)
    if tool_call_info:
        _log_turn(visit_id, session_id, "tool_call", tool_call_info["name"])
        _log_turn(visit_id, session_id, "tool_result", json.dumps(tool_call_info["result"]))
    _log_turn(visit_id, session_id, "assistant", reply_with_disclaimer)

    return jsonify({"reply": reply_with_disclaimer})
