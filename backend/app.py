import os
import logging
from datetime import datetime, timedelta, timezone

from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv
from apscheduler.schedulers.background import BackgroundScheduler

from db import init_db
from mail import init_mail
from health_feed import run_health_feed_job
from analytics import run_weekly_analytics_job
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
from routes.patients import patients_bp
from routes.analytics import analytics_bp

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
    # Flask's itsdangerous signer embeds a timestamp in every session cookie and
    # checks it against this value on every request (flask/sessions.py's
    # open_session -> max_age), regardless of session.permanent - a replayed cookie
    # is rejected server-side the same way whether or not the browser would have
    # honored its Expires header. Without this line Flask silently defaults to 31
    # days. session.permanent = True at login (routes/auth.py) additionally makes
    # the cookie's own Expires header match this window and turns it into a sliding
    # idle-timeout (refreshed on each active request, per Flask's default
    # SESSION_REFRESH_EACH_REQUEST=True) rather than a fixed one anchored to login.
    app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(
        seconds=int(os.environ.get("SESSION_LIFETIME_SECONDS", 28800))
    )

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
    app.register_blueprint(patients_bp)
    app.register_blueprint(analytics_bp)

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

# This used to guard against the Werkzeug dev reloader importing this module
# twice (once in the monitor process, once in the actual serving child) and
# starting two competing schedulers. Debug/reload is now hard-disabled below
# (see the app.run() call) regardless of FLASK_ENV, so Werkzeug never spawns a
# reloader child and this module is only ever imported once per process - the
# scheduler always starts exactly once, the same way it already did in
# production (gunicorn, no reloader, single worker per the Procfile).
# Coordinating a scheduler across multiple gunicorn workers is a separate
# problem, deferred - see docs/SECURITY_NOTES.md.
scheduler = BackgroundScheduler()
scheduler.add_job(run_health_feed_job, "interval", hours=12, id="health_feed_job")
scheduler.add_job(run_weekly_analytics_job, "interval", days=7, id="weekly_analytics_job")
scheduler.start()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    # Hard override, independent of FLASK_ENV: the Werkzeug interactive debugger
    # must never be reachable. /api/login and /api/checkin are both unauthenticated
    # by design, so an unhandled exception on either path would otherwise hand an
    # anonymous caller a remote-code-execution console. FLASK_ENV still governs
    # CORS origins and the SESSION_COOKIE_SECURE relaxation above - only this one
    # debug flag is hard-pinned, so re-adding FLASK_ENV=development later (for
    # those other reasons) can't silently turn this back on. gunicorn (see
    # Procfile) never executes this __main__ block at all, so it is unaffected
    # either way.
    app.run(host="0.0.0.0", port=port, debug=False)
