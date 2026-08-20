import logging
from functools import wraps
from flask import session, jsonify

from db import get_db

logger = logging.getLogger(__name__)


def is_session_valid():
    """True only if session["staff_id"] still names a real staff_users row AND
    that row's current session_version matches what was stamped into this
    session at login. Catches both a deleted/missing account (no row to compare
    against) and a session issued before the account's most recent logout
    (version bumped there, no longer matches here) - see routes/auth.py."""
    staff_id = session.get("staff_id")
    if not staff_id:
        return False

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT session_version FROM staff_users WHERE id = ?", (staff_id,))
    row = cur.fetchone()
    conn.close()

    if not row:
        return False

    return row["session_version"] == session.get("session_version")


def require_staff_login(view_func):
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if not is_session_valid():
            return jsonify({"error": "authentication required"}), 401
        return view_func(*args, **kwargs)
    return wrapped
