import os
import logging
from datetime import datetime, timezone

from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv
from apscheduler.schedulers.background import BackgroundScheduler

from db import init_db
from mail import init_mail
from health_feed import run_health_feed_job
from rate_limit import limiter

from routes.checkin import checkin_bp
from routes.queue import queue_bp
from routes.visits import visits_bp
from routes.audit import audit_bp
from routes.health import health_bp
from routes.auth import auth_bp
from routes.patient_chat import patient_chat_bp
from routes.staff_chat import staff_chat_bp
from routes.config import config_bp
from routes.doctors import doctors_bp
from routes.appointments import appointments_bp

load_dotenv()

FRONTEND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'frontend')

ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.environ.get("ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",")
]

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

REQUIRED_ENV_VARS = ("SECRET_KEY", "ANTHROPIC_API_KEY", "MAIL_USERNAME", "MAIL_PASSWORD")


def _validate_required_env():
    missing = [name for name in REQUIRED_ENV_VARS if not os.environ.get(name)]
    if missing:
        raise RuntimeError(
            f"Missing required environment variable(s): {', '.join(missing)}. "
            f"Copy backend/.env.example to backend/.env and fill in real values."
        )


def create_app():
    _validate_required_env()
    app = Flask(__name__)

    app.secret_key = os.environ.get("SECRET_KEY")
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["SESSION_COOKIE_SECURE"] = os.environ.get("FLASK_ENV") != "development"

    CORS(app, supports_credentials=True, origins=ALLOWED_ORIGINS)

    init_db()
    init_mail(app)
    limiter.init_app(app)

    app.register_blueprint(checkin_bp)
    app.register_blueprint(queue_bp)
    app.register_blueprint(visits_bp)
    app.register_blueprint(audit_bp)
    app.register_blueprint(health_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(patient_chat_bp)
    app.register_blueprint(staff_chat_bp)
    app.register_blueprint(config_bp)
    app.register_blueprint(doctors_bp)
    app.register_blueprint(appointments_bp)

    @app.route("/api/ping")
    def ping():
        return jsonify({
            "status": "ok",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    @app.route("/api/config")
    def config():
        return jsonify({
            "dashboard_url": os.environ.get("DASHBOARD_URL", "http://localhost:3000"),
        })

    @app.route('/')
    def index():
        return send_from_directory(FRONTEND_DIR, 'index.html')

    @app.route('/checkin')
    def checkin():
        return send_from_directory(FRONTEND_DIR, 'checkin.html')

    @app.route('/triage')
    def triage_page():
        return send_from_directory(FRONTEND_DIR, 'triage.html')

    @app.route('/booking')
    def booking_page():
        return send_from_directory(FRONTEND_DIR, 'booking.html')

    @app.route('/status')
    def status_page():
        return send_from_directory(FRONTEND_DIR, 'status.html')

    @app.route('/login')
    def login_page():
        return send_from_directory(FRONTEND_DIR, 'login.html')

    @app.route('/frontend/<path:filename>')
    def frontend_static(filename):
        return send_from_directory(FRONTEND_DIR, filename)

    return app


app = create_app()

# Guard against the Werkzeug dev reloader importing this module twice (once in
# the monitor process, once in the actual serving child) and starting two
# competing schedulers. In production (gunicorn, no reloader) FLASK_ENV is not
# "development" so this always starts exactly once on the single worker
# defined in the Procfile. Coordinating a scheduler across multiple gunicorn
# workers is a separate problem, deferred - see docs/SECURITY_NOTES.md.
_is_reloader_child = os.environ.get("WERKZEUG_RUN_MAIN") == "true"
_reloader_active = os.environ.get("FLASK_ENV") == "development"

if _is_reloader_child or not _reloader_active:
    scheduler = BackgroundScheduler()
    scheduler.add_job(run_health_feed_job, "interval", hours=12, id="health_feed_job")
    scheduler.start()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=(os.environ.get("FLASK_ENV") == "development"))
