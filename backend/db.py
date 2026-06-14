import os
import sqlite3
import uuid
from datetime import datetime, timezone

DATABASE_PATH = os.environ.get("DATABASE_PATH", "careflow.db")

WAIT_TIMES = {
    "gp_consult": 15,
    "prescription_renewal": 8,
    "injury": 12,
    "general": 10,
}

ACTIVE_STATUSES_EXCLUDE = ("completed", "no_show")


def get_db():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS visits (
            id TEXT PRIMARY KEY,
            name TEXT,
            visit_type TEXT,
            email TEXT,
            phone TEXT,
            queue_position INTEGER,
            priority_level TEXT,
            triage_summary TEXT,
            flag_reason TEXT,
            status TEXT DEFAULT 'checked_in',
            estimated_wait INTEGER,
            actual_wait INTEGER,
            health_alert_match INTEGER DEFAULT 0,
            position3_notified INTEGER DEFAULT 0,
            created_at TEXT,
            updated_at TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS health_feed (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entries TEXT,
            fetched_at TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            visit_id TEXT,
            patient_name TEXT,
            event_type TEXT,
            old_status TEXT,
            new_status TEXT,
            timestamp TEXT,
            actor TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS appointments (
            id TEXT PRIMARY KEY,
            name TEXT,
            visit_type TEXT,
            email TEXT,
            phone TEXT,
            slot_time TEXT,
            status TEXT DEFAULT 'booked',
            created_at TEXT
        )
    """)

    conn.commit()
    conn.close()


def generate_id():
    return uuid.uuid4().hex[:8]


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def calculate_wait(visit_type, queue_position):
    average = WAIT_TIMES.get(visit_type, WAIT_TIMES["general"])
    return average * queue_position


def get_next_queue_position():
    conn = get_db()
    cur = conn.cursor()
    placeholders = ",".join("?" for _ in ACTIVE_STATUSES_EXCLUDE)
    cur.execute(
        f"SELECT COUNT(*) AS count FROM visits WHERE status NOT IN ({placeholders})",
        ACTIVE_STATUSES_EXCLUDE,
    )
    count = cur.fetchone()["count"]
    conn.close()
    return count + 1
