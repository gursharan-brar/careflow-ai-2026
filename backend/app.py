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

from routes.checkin import checkin_bp
from routes.queue import queue_bp
from routes.visits import visits_bp
from routes.audit import audit_bp
from routes.health import health_bp

load_dotenv()

FRONTEND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'frontend')

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def create_app():
    app = Flask(__name__)
    CORS(app)

    init_db()
    init_mail(app)

    app.register_blueprint(checkin_bp)
    app.register_blueprint(queue_bp)
    app.register_blueprint(visits_bp)
    app.register_blueprint(audit_bp)
    app.register_blueprint(health_bp)

    @app.route("/api/ping")
    def ping():
        return jsonify({
            "status": "ok",
            "timestamp": datetime.now(timezone.utc).isoformat(),
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

    @app.route('/status')
    def status_page():
        return send_from_directory(FRONTEND_DIR, 'status.html')

    @app.route('/frontend/<path:filename>')
    def frontend_static(filename):
        return send_from_directory(FRONTEND_DIR, filename)

    return app


app = create_app()

scheduler = BackgroundScheduler()
scheduler.add_job(run_health_feed_job, "interval", hours=12, id="health_feed_job")
scheduler.start()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=(os.environ.get("FLASK_ENV") == "development"))
