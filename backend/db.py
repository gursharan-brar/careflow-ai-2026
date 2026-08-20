import os
import re
import math
import logging
import sqlite3
import uuid
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

DATABASE_PATH = os.environ.get("DATABASE_PATH", "careflow.db")

# Alberta Personal Health Number (PHN) format: exactly 9 digits, numeric only.
# Shared between routes/checkin.py and routes/appointments.py so both entry
# points enforce the identical format check.
HEALTH_ID_REGEX = re.compile(r"^\d{9}$")

WAIT_TIMES = {
    "gp_consult": 15,
    "prescription_renewal": 8,
    "injury": 12,
    "general": 10,
}

# Beyond ~90 min an estimate stops being a useful number and a clinic would
# intervene operationally (call in more staff, redirect patients) before a
# real queue ever got this deep — so the formula should never display more.
MAX_DISPLAYED_WAIT_MINUTES = 90

ACTIVE_STATUSES_EXCLUDE = ("completed", "no_show")

# Minimum realistic staffing for a Calgary walk-in clinic.
DEFAULT_DOCTORS_ON_SHIFT = 3

ACTIVE_DOCTOR_STATUSES_EXCLUDE = ("inactive",)

# Same-day booking operates on fixed 30-minute slots across the clinic's
# operating hours (08:00-17:00 inclusive), independent of any one doctor's
# actual shift times — a clinic-wide booking grid rather than per-doctor hours.
BOOKING_DAY_START_MINUTES = 8 * 60
BOOKING_DAY_END_MINUTES = 17 * 60
BOOKING_SLOT_INTERVAL_MINUTES = 30

APPOINTMENT_ACTIVE_STATUSES_EXCLUDE = ("cancelled",)


def generate_booking_slots():
    """Fixed 30-minute slot start times ("HH:MM") for the clinic's booking day.
    17:00 is the clinic's close time, not a bookable start — the last slot is
    16:30 (covering 16:30-17:00), giving 18 slots total from 08:00."""
    slots = []
    minutes = BOOKING_DAY_START_MINUTES
    while minutes < BOOKING_DAY_END_MINUTES:
        slots.append(f"{minutes // 60:02d}:{minutes % 60:02d}")
        minutes += BOOKING_SLOT_INTERVAL_MINUTES
    return slots


BOOKING_SLOTS = generate_booking_slots()

PLACEHOLDER_DOCTORS = (
    (1, "Dr. Priya Sharma"),
    (2, "Dr. James Okafor"),
    (3, "Dr. Sarah Mitchell"),
    (4, "Dr. Harjit Bains"),
    (5, "Dr. Elena Vasquez"),
)

# Names this seed used before the real-name rename (2026-06) — used only as a
# WHERE guard for the one-time UPDATE migration below, so a clinic admin who
# has since renamed a doctor through the API is never silently overwritten.
_LEGACY_PLACEHOLDER_NAMES = {
    1: "Doctor 1",
    2: "Doctor 2",
    3: "Doctor 3",
    4: "Doctor 4",
    5: "Doctor 5",
}

# calculate_wait() reads doctors_on_shift on every call (including once per row
# during a staff dashboard queue poll), so config reads are cached briefly in
# memory rather than hitting SQLite on every row. set_config() writes through
# this cache immediately so a staff change is reflected without waiting out
# the TTL.
_CONFIG_CACHE_TTL_SECONDS = 30
_config_cache = {}


def get_db():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def get_db_for_transaction():
    """Autocommit-mode connection for callers that need to manage their own
    BEGIN IMMEDIATE / COMMIT / ROLLBACK around multiple statements atomically."""
    conn = sqlite3.connect(DATABASE_PATH, isolation_level=None)
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

    # Same shape/pattern as health_feed above: one row per generation, most
    # recent read by ORDER BY id DESC LIMIT 1 (see routes/analytics.py).
    cur.execute("""
        CREATE TABLE IF NOT EXISTS weekly_analytics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stats_json TEXT,
            summary_text TEXT,
            generated_at TEXT
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
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            doctor_id INTEGER NOT NULL REFERENCES doctors(id),
            patient_name TEXT NOT NULL,
            patient_email TEXT NOT NULL,
            patient_phone TEXT,
            slot_time TEXT NOT NULL,
            slot_date TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'confirmed'
                CHECK (status IN ('confirmed', 'cancelled', 'completed')),
            visit_id TEXT REFERENCES visits(id) DEFAULT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Pre-existing installs already have an "appointments" table from an earlier,
    # never-wired-up attempt at this feature (TEXT id, no doctor_id/slot_date) —
    # CREATE TABLE IF NOT EXISTS above is a no-op against it. That old table was
    # confirmed empty and referenced by zero code paths, so it's safe to replace
    # outright; the empty-check is kept here as a guard against ever silently
    # dropping real data if that assumption stops holding.
    cur.execute("PRAGMA table_info(appointments)")
    appointment_columns = {row["name"] for row in cur.fetchall()}
    if "doctor_id" not in appointment_columns:
        cur.execute("SELECT COUNT(*) AS count FROM appointments")
        if cur.fetchone()["count"] == 0:
            cur.execute("DROP TABLE appointments")
            cur.execute("""
                CREATE TABLE appointments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    doctor_id INTEGER NOT NULL REFERENCES doctors(id),
                    patient_name TEXT NOT NULL,
                    patient_email TEXT NOT NULL,
                    patient_phone TEXT,
                    slot_time TEXT NOT NULL,
                    slot_date TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'confirmed'
                        CHECK (status IN ('confirmed', 'cancelled', 'completed')),
                    visit_id TEXT REFERENCES visits(id) DEFAULT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

    # Re-checked fresh (not reusing appointment_columns above) since the legacy
    # DROP/CREATE branch just above may have just rebuilt the table without it.
    cur.execute("PRAGMA table_info(appointments)")
    appointment_columns = {row["name"] for row in cur.fetchall()}
    if "health_id" not in appointment_columns:
        # Alberta Personal Health Number (PHN), collected at booking (see
        # routes/appointments.py) so a duplicate-active-appointment check can
        # be scoped to it, same as the visits-side guard in routes/checkin.py.
        cur.execute("ALTER TABLE appointments ADD COLUMN health_id TEXT DEFAULT NULL")
        logger.info("Migrated appointments table: added health_id column")

    cur.execute("""
        CREATE TABLE IF NOT EXISTS staff_users (
            id TEXT PRIMARY KEY,
            username TEXT UNIQUE,
            password_hash TEXT,
            display_name TEXT,
            created_at TEXT
        )
    """)

    cur.execute("PRAGMA table_info(staff_users)")
    staff_user_columns = {row["name"] for row in cur.fetchall()}
    if "session_version" not in staff_user_columns:
        # Bumped on logout (see routes/auth.py) so every previously-issued signed
        # session cookie for that account - including one captured before logout -
        # stops passing require_staff_login's check immediately, without needing
        # any server-side session storage. A session whose staff_id no longer has
        # a matching row at all (account deleted) is rejected the same way, by the
        # same lookup finding nothing to compare against.
        cur.execute("ALTER TABLE staff_users ADD COLUMN session_version INTEGER NOT NULL DEFAULT 1")
        logger.info("Migrated staff_users table: added session_version column")

    cur.execute("""
        CREATE TABLE IF NOT EXISTS chat_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_type TEXT,
            visit_id TEXT,
            staff_id TEXT,
            session_id TEXT,
            role TEXT,
            content TEXT,
            created_at TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS clinic_config (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT UNIQUE NOT NULL,
            value TEXT NOT NULL,
            updated_at TEXT
        )
    """)

    cur.execute(
        "INSERT OR IGNORE INTO clinic_config (key, value, updated_at) VALUES (?, ?, ?)",
        ("doctors_on_shift", str(DEFAULT_DOCTORS_ON_SHIFT), now_iso()),
    )

    cur.execute("""
        CREATE TABLE IF NOT EXISTS doctors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'off_shift'
                CHECK (status IN ('on_shift', 'off_shift', 'inactive')),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    for doctor_id, doctor_name in PLACEHOLDER_DOCTORS:
        cur.execute(
            "INSERT OR IGNORE INTO doctors (id, name, status) VALUES (?, ?, 'off_shift')",
            (doctor_id, doctor_name),
        )

    # INSERT OR IGNORE above only fires on first-ever boot. Existing installs
    # already have rows seeded under the old "Doctor N" placeholder names, so
    # rename those rows in place — guarded by the legacy name so a doctor a
    # clinic admin has already renamed through the API is never overwritten.
    for doctor_id, real_name in PLACEHOLDER_DOCTORS:
        legacy_name = _LEGACY_PLACEHOLDER_NAMES.get(doctor_id)
        if legacy_name:
            cur.execute(
                "UPDATE doctors SET name = ?, updated_at = ? WHERE id = ? AND name = ?",
                (real_name, now_iso(), doctor_id, legacy_name),
            )

    # visits predates the doctor-assignment feature, so the column is added via
    # migration rather than the CREATE TABLE above — only once, idempotently.
    cur.execute("PRAGMA table_info(visits)")
    visit_columns = {row["name"] for row in cur.fetchall()}
    if "doctor_id" not in visit_columns:
        cur.execute("ALTER TABLE visits ADD COLUMN doctor_id INTEGER REFERENCES doctors(id) DEFAULT NULL")
    if "booked_slot_time" not in visit_columns:
        # Set when a visit was created from a same-day booking's "Arrived" action
        # (see routes/appointments.py) rather than a walk-in check-in. Lets the
        # queue sort booked arrivals to the front of their doctor's lane by their
        # original slot time, with walk-ins following by check-in order.
        cur.execute("ALTER TABLE visits ADD COLUMN booked_slot_time TEXT DEFAULT NULL")
    if "triage_answers" not in visit_columns:
        # JSON-encoded array of {"question": ..., "answer": ...} pairs, written by
        # POST /api/triage before the Claude call so the patient's raw answers are
        # never lost even if classify_triage() fails (see routes/checkin.py).
        cur.execute("ALTER TABLE visits ADD COLUMN triage_answers TEXT DEFAULT NULL")
        logger.info("Migrated visits table: added triage_answers column")
    if "health_id" not in visit_columns:
        # Alberta Personal Health Number (PHN), collected at check-in. Validated
        # server-side as 9 digits only (see routes/checkin.py) - format check,
        # not a lookup against any registry - so it's stored as-is, nullable
        # since it's added after visits already existed.
        cur.execute("ALTER TABLE visits ADD COLUMN health_id TEXT DEFAULT NULL")
        logger.info("Migrated visits table: added health_id column")
    if "needs_doctor_reassignment" not in visit_columns:
        # Explicitly set by convert_appointment_to_visit() (routes/appointments.py)
        # at the moment a check-in merge finds the originally-booked doctor is no
        # longer on shift and skips pre-assignment. Never inferred after the fact
        # from booked_slot_time/doctor_id - that combination is only correct today
        # because Arrived always assigns a doctor, and would silently break if
        # anything else ever created an unassigned visit with a booked_slot_time.
        cur.execute("ALTER TABLE visits ADD COLUMN needs_doctor_reassignment INTEGER DEFAULT 0")
        logger.info("Migrated visits table: added needs_doctor_reassignment column")
    if "stale_slot_at_checkin" not in visit_columns:
        # Set only by the check-in merge path (routes/checkin.py) when the matched
        # confirmed appointment's slot_time had already passed at the moment of
        # check-in. Stores the original "HH:MM" slot string, or NULL. A point-in-time
        # fact captured once, not something recomputable later - a same-day slot
        # would trivially read as "passed" if compared against the current clock
        # instead of what was actually true at check-in time.
        cur.execute("ALTER TABLE visits ADD COLUMN stale_slot_at_checkin TEXT DEFAULT NULL")
        logger.info("Migrated visits table: added stale_slot_at_checkin column")

    conn.commit()
    conn.close()


def generate_id():
    return str(uuid.uuid4())


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def get_config(key, default=None):
    cached = _config_cache.get(key)
    now = datetime.now(timezone.utc).timestamp()
    if cached is not None and (now - cached[1]) < _CONFIG_CACHE_TTL_SECONDS:
        return cached[0]

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT value FROM clinic_config WHERE key = ?", (key,))
    row = cur.fetchone()
    conn.close()

    value = row["value"] if row else default
    _config_cache[key] = (value, now)
    return value


def set_config(key, value):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO clinic_config (key, value, updated_at) VALUES (?, ?, ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
        """,
        (key, str(value), now_iso()),
    )
    conn.commit()
    conn.close()
    _config_cache[key] = (str(value), datetime.now(timezone.utc).timestamp())


def calculate_wait(visit_type, queue_position):
    average = WAIT_TIMES.get(visit_type, WAIT_TIMES["general"])
    doctors_on_shift = max(1, int(get_config("doctors_on_shift", DEFAULT_DOCTORS_ON_SHIFT)))
    shifts = math.ceil(queue_position / doctors_on_shift)
    return min(average * shifts, MAX_DISPLAYED_WAIT_MINUTES)


def calculate_doctor_wait(visit_type, doctor_position):
    """Live staff-dashboard estimate for a patient already assigned to a specific
    doctor: position within that one doctor's queue, not the global queue.
    Unassigned patients never reach this function — callers should set
    estimated_wait to None directly instead."""
    average = WAIT_TIMES.get(visit_type, WAIT_TIMES["general"])
    return min(average * doctor_position, MAX_DISPLAYED_WAIT_MINUTES)


def get_doctor_position(cur, doctor_id, queue_position):
    """Position of a visit within its assigned doctor's own queue (not the
    global queue) — count of that doctor's other active patients who checked
    in earlier, plus one for the patient itself."""
    placeholders = ",".join("?" for _ in ACTIVE_STATUSES_EXCLUDE)
    cur.execute(
        f"""
        SELECT COUNT(*) AS count FROM visits
        WHERE doctor_id = ? AND status NOT IN ({placeholders}) AND queue_position < ?
        """,
        (doctor_id, *ACTIVE_STATUSES_EXCLUDE, queue_position),
    )
    return cur.fetchone()["count"] + 1


def get_next_queue_position(cur):
    """Must be called on a cursor already inside a BEGIN IMMEDIATE transaction
    so the count-then-insert in the caller can't interleave with another
    concurrent check-in."""
    placeholders = ",".join("?" for _ in ACTIVE_STATUSES_EXCLUDE)
    cur.execute(
        f"SELECT COUNT(*) AS count FROM visits WHERE status NOT IN ({placeholders})",
        ACTIVE_STATUSES_EXCLUDE,
    )
    count = cur.fetchone()["count"]
    return count + 1
