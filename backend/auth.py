import logging
from functools import wraps
from flask import session, jsonify

logger = logging.getLogger(__name__)


def require_staff_login(view_func):
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if not session.get("staff_id"):
            return jsonify({"error": "authentication required"}), 401
        return view_func(*args, **kwargs)
    return wrapped
