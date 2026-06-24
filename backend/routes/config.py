from flask import Blueprint, request, jsonify

from db import get_config, set_config, DEFAULT_DOCTORS_ON_SHIFT
from auth import require_staff_login

config_bp = Blueprint("config", __name__)

MIN_DOCTORS_ON_SHIFT = 1
MAX_DOCTORS_ON_SHIFT = 10


@config_bp.route("/api/config/doctors", methods=["GET"])
@require_staff_login
def get_doctors_on_shift():
    value = int(get_config("doctors_on_shift", DEFAULT_DOCTORS_ON_SHIFT))
    return jsonify({"doctors_on_shift": value})


@config_bp.route("/api/config/doctors", methods=["PATCH"])
@require_staff_login
def update_doctors_on_shift():
    data = request.get_json(silent=True) or {}
    value = data.get("doctors_on_shift")

    if not isinstance(value, int) or isinstance(value, bool):
        return jsonify({"error": "doctors_on_shift must be an integer"}), 400

    if value < MIN_DOCTORS_ON_SHIFT or value > MAX_DOCTORS_ON_SHIFT:
        return jsonify({
            "error": f"doctors_on_shift must be between {MIN_DOCTORS_ON_SHIFT} and {MAX_DOCTORS_ON_SHIFT}"
        }), 400

    set_config("doctors_on_shift", value)
    return jsonify({"doctors_on_shift": value})
