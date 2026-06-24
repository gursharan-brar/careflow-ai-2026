# Security Notes

This document tracks the security remediation pass performed against the
critical/high findings from the security audit, and records what was
deliberately deferred and why.

## Full inventory of security protocols currently in effect

This section is a complete, file-by-file inventory of every security-relevant
decision currently live in the codebase — not just what changed in the most
recent pass. Treat it as the source of truth for "what do we already do"
before proposing new work.

### Secrets & configuration
- `backend/.env` is never committed — excluded by both `.gitignore` (root)
  and `backend/.gitignore`, independently, along with `*.db`, `.venv/`,
  `__pycache__/`, `*.pyc`, `build/`, `node_modules/`.
- `backend/.env.example` documents every required variable with placeholder
  values so the repo is self-describing without ever holding a real secret.
- `create_app()` in `app.py` fails fast at startup if `SECRET_KEY`,
  `ANTHROPIC_API_KEY`, `MAIL_USERNAME`, or `MAIL_PASSWORD` is missing, instead
  of starting in a silently broken or insecure state.
- `MAIL_PASSWORD` has spaces stripped (`mail.py`) to accept a copy-pasted
  Gmail App Password, without ever logging the value.
- `DATABASE_PATH` and `PORT` are env-configurable, not hardcoded.

### Authentication (`auth.py`, `routes/auth.py`, `seed_staff.py`)
- There is no public registration endpoint. `seed_staff.py` is the *only*
  way a `staff_users` row is ever created — a CLI script run by a developer
  with direct DB access, using `getpass` so the password is never echoed to
  the terminal or shell history, and requiring a matching confirmation entry.
- Passwords are hashed with Werkzeug's `generate_password_hash` /
  `check_password_hash` (salted) — never stored or compared in plaintext.
- `POST /api/login` checks username and password are both non-empty before
  touching the DB, and returns the same generic `"invalid credentials"` for
  an unknown username and a wrong password alike, so the error response
  can't be used to enumerate valid usernames.
- Sessions are server-side (Flask `session`, signed with `SECRET_KEY`), not
  a token held in `localStorage` — nothing readable by client-side JS or an
  XSS payload carries the auth state itself.
- `POST /api/logout` calls `session.clear()`, dropping all session keys, not
  just `staff_id`.

### Authorization
- `require_staff_login` (`auth.py`) gates: `GET /api/queue`,
  `PATCH /api/visit/<id>/status`, `GET /api/audit`, `GET /api/health-feed`,
  `POST /api/chat/staff`. All staff-only data and all state-changing visit
  actions require a logged-in session.
- `GET /api/visit/<id>`, `POST /api/checkin`, `POST /api/triage`, and
  `POST /api/chat/patient` are intentionally public — patients have no
  account, so these endpoints carry their own input validation instead
  (see below) rather than auth.

### Session / cookie hardening (`app.py`)
- `SESSION_COOKIE_SAMESITE = "Lax"` on every session cookie.
- `SESSION_COOKIE_SECURE` is `True` in any non-development environment, only
  relaxed when `FLASK_ENV=development` so local HTTP testing still works.

### CORS (`app.py`)
- `CORS(app, supports_credentials=True, origins=ALLOWED_ORIGINS)` — an
  explicit allowlist read from env, never a wildcard `*` (which browsers
  reject anyway when combined with credentials, but the code doesn't rely
  on that — it's explicit).
- `login.html` and the dashboard send `credentials: "include"` to match.

### Rate limiting (`rate_limit.py`, applied per-route)
- `POST /api/login`: 5/minute/IP — brute-force throttling.
- `POST /api/checkin`, `POST /api/triage`, `POST /api/chat/patient`,
  `POST /api/chat/staff`: 30/minute/IP — abuse and cost throttling (these are
  the routes that call the paid Anthropic API or write to the DB on every
  hit).
- Limiter is keyed by remote address, so the limit is per-source-IP, not
  global across all users.

### Input validation & injection prevention
- Every SQL query across `db.py` and every route uses parameterized `?`
  placeholders — there is no string-interpolated SQL anywhere in the
  codebase, so there is no SQL injection surface.
- `request.get_json(silent=True)` is used at every route — malformed JSON
  degrades to `{}` and a clean `400`, instead of an unhandled exception
  leaking a stack trace.
- Check-in: email validated against `EMAIL_REGEX`, `visit_type` checked
  against an explicit allowlist tuple, and name/email/phone length-capped
  (100/254/20 chars) before anything touches the DB.
- Triage: `symptom_answers` is strictly validated as a list of exactly 5
  strings before being interpolated into the AI prompt.
- Chat: message capped at 2000 chars, history capped at 50 turns, both
  enforced server-side regardless of what the client sends.

### IDOR / identifier design
- Visit IDs are full `uuid4()` strings (`db.py`) — unguessable, not
  sequential or derived from an 8-char slice as before.
- The visit status machine (`VALID_TRANSITIONS` in `visits.py`) is enforced
  server-side; a client cannot jump a visit straight to `completed` or
  transition out of a terminal state.
- `POST /api/triage` is single-submit: a second call for a visit that
  already has a `triage_summary` returns `409 Conflict` instead of silently
  overwriting clinical data.
- The audit log's `actor` field is derived from `session["staff_name"]`
  server-side in `PATCH /api/visit/<id>/status` — never trusted from the
  request body, so a logged-in staff member cannot spoof another staff
  member as the actor of an action.

### Race conditions / data integrity (`db.py`, `routes/checkin.py`)
- Queue-position assignment runs inside a `BEGIN IMMEDIATE` transaction
  (`get_db_for_transaction()` + `get_next_queue_position(cur)`), so the
  count-then-insert for two simultaneous check-ins can't interleave into a
  duplicate position.
- `position3_notified` is flipped to `1` only via an `on_success` callback
  invoked after the email actually sends (`mail.py` /
  `routes/queue.py`) — a failed send leaves it `0` so it's retried on the
  next poll instead of being silently lost.

### AI / LLM-specific safety (`triage.py`, `health_feed.py`, `patient_chat.py`, `staff_chat.py`)
- Both chat system prompts explicitly declare their data-access boundaries
  ("you do not have access to...") and explicitly instruct the model to
  ignore any in-conversation attempt to change its rules, reveal system
  instructions, or claim access it doesn't have — a prompt-injection
  guardrail baked into the system prompt itself.
- The patient chatbot is explicitly forbidden from giving medical advice or
  interpreting symptoms; it redirects medical questions to the structured,
  audited check-in/triage flow instead of answering free-form — keeps
  clinically-sensitive judgment inside the path that's actually validated
  and logged.
- Model output is never trusted as-is. Triage and health-feed responses are
  extracted via regex, parsed with `json.loads`, and field-validated
  (`priority_level` checked against an explicit allowlist, required fields
  checked non-empty) before being stored. Any parse/validation failure falls
  back to a safe static default — `moderate` priority flagged for manual
  review (triage), or a clearly-labeled "feed unavailable" placeholder
  (health feed) — rather than storing malformed data or crashing.
- All four Claude call sites (`triage.py`, `health_feed.py`,
  `patient_chat.py`, `staff_chat.py`) wrap the API call in `try/except` and
  log the failure rather than letting an upstream API error surface a stack
  trace or 500 to the patient or staff member.

### Email (`mail.py`)
- SMTP runs over implicit SSL (port 465, `MAIL_USE_SSL=True`), not
  plaintext.
- Sending happens on a background daemon thread, so a slow or failed SMTP
  call can't block or crash the request handler; failures are caught and
  logged, not raised.
- Mail credentials are read only from env and never appear in a log line.

### Client-side / frontend
- `chat-widget.js` renders every message via `.textContent`, never
  `.innerHTML` — neither a user's typed message nor the model's reply can
  ever inject HTML or script into the page. This makes the chat widget
  XSS-safe by construction regardless of what the model returns.
- `login.html` uses correct semantic `autocomplete="username"` /
  `autocomplete="current-password"` attributes rather than disabling
  autocomplete (which would push users toward insecure workarounds).
- The anonymous patient-chat session ID (`chat-widget.js`) is a random,
  non-sensitive string stored in `localStorage` only when there is no
  `visit_id` in the URL — a chat tied to a specific patient visit is never
  persisted to that shared browser's local storage.
- The staff dashboard redirect URL is fetched at runtime from
  `GET /api/config` rather than hardcoded into shipped HTML.

### Deployment / process hygiene
- `Procfile` runs `gunicorn app:app`, a production WSGI server — the Flask
  dev server (`app.run(...)`) only ever executes under
  `if __name__ == "__main__"`, i.e. local development.
- The APScheduler health-feed job is guarded (`WERKZEUG_RUN_MAIN`,
  `FLASK_ENV`) so it starts exactly once under the dev reloader instead of
  twice, avoiding duplicate paid API calls in local dev.

## Fixed in this pass

**Phase 1 - Immediate containment**
- Confirmed `backend/.env` is not and has never been tracked by git (verified
  via `git ls-files`); no history cleanup was needed.
- Added `backend/.env.example` listing every required environment variable
  with placeholder values, so the team can provision a working `.env`
  without secrets ever being committed.
- Added fail-fast startup validation in `app.py`: `create_app()` now checks
  `SECRET_KEY`, `ANTHROPIC_API_KEY`, `MAIL_USERNAME`, and `MAIL_PASSWORD` are
  present and non-empty, and raises a clear `RuntimeError` naming the missing
  variable(s) instead of starting in a silently broken state.

**Phase 2 - Fast, safe fixes**
- **UUID4 visit IDs** - `generate_id()` in `db.py` now returns a full
  `uuid4()` string instead of an 8-char hex slice, making visit IDs
  unguessable. Verified end-to-end (check-in -> triage -> status) with the
  new ID format; confirmed no code anywhere assumed the old 8-character
  length.
- **Triage single-use guard** - `POST /api/triage` now rejects a second
  submission for the same `visit_id` with `409 Conflict` if `triage_summary`
  is already set, instead of silently overwriting it. Verified: first
  submission succeeds, second is rejected, original data is unchanged.
- **Audit actor fix** - `PATCH /api/visit/<id>/status` no longer trusts an
  `actor` field from the request body. The actor is now derived from
  `session["staff_name"]` for the logged-in staff member making the request.
  The dashboard (`QueuePanel.js`) no longer sends a fake `actor` field.
  Verified: a request with a spoofed `actor` in the body is ignored and the
  audit log correctly shows the real logged-in staff member.
- **Rate limiting** - Added Flask-Limiter. `POST /api/login` is limited to 5
  attempts/minute/IP; `POST /api/checkin`, `POST /api/triage`,
  `POST /api/chat/patient`, and `POST /api/chat/staff` are limited to 30
  requests/minute/IP. Verified: normal traffic (10-15 rapid requests) is
  unaffected; a 6th rapid login attempt within a minute is throttled with
  `429`, including for valid credentials (the limit is per-IP, not
  per-outcome, by design - it resets after a minute and never permanently
  locks an account).
- **Input length caps** - Added max-length validation for patient name (100),
  email (254), phone (20) on check-in, and chat message content (2000) and
  history array length (50 turns) on both chat endpoints. Oversized input is
  rejected with a clear `400`, not silently truncated. Verified with both
  normal and intentionally oversized (50,000-character) payloads.
- **Queue position race condition** - Check-in now reads the current queue
  count and inserts the new visit inside a single `BEGIN IMMEDIATE`
  transaction (`get_db_for_transaction()` / `get_next_queue_position(cur)` in
  `db.py`), so the read-then-insert can no longer interleave between two
  concurrent check-ins. Verified with an actual concurrency test: 15
  simultaneous check-in requests produced 15 unique, sequential queue
  positions with zero duplicates.
- **`position3_notified` ordering** - The position-3 notification flag is no
  longer set before the email is sent. `send_position3_email()` now accepts
  an `on_success` callback that flips `position3_notified` to 1 only after
  the send actually succeeds; a failed send leaves it at 0 so it's eligible
  to be retried on the next queue poll. Verified both directions: a
  successful send flips the flag (confirmed it stays 0 immediately after the
  request and becomes 1 only after the async send completes), and a
  simulated send failure never invokes the callback.
- **Environment-driven dashboard redirect** - `login.html` no longer
  hardcodes `http://localhost:3000`. It now fetches the dashboard URL from a
  new public `GET /api/config` endpoint that reads `DASHBOARD_URL` from the
  environment (same pattern as the existing `ALLOWED_ORIGINS` variable).
  Verified end-to-end: a successful login redirects to the URL returned by
  `/api/config`, not a hardcoded string.
- **Scheduler duplication guard** - The APScheduler health-feed job in
  `app.py` is now gated so it only starts in the actual serving process, not
  the Werkzeug dev-reloader's monitor process (checked via
  `WERKZEUG_RUN_MAIN` and `FLASK_ENV`). Verified the guard logic against all
  three real scenarios: dev-mode monitor process (does not start), dev-mode
  reloaded child (starts), and production/no-reloader (starts once).

## Known limitations - deferred by design

These were identified in the audit and intentionally **not** fixed in this
pass. Each is a reasonable next step for a production deployment, not a
capstone-timeline priority.

- **Signed/expiring patient tokens.** Today, anyone who has (or guesses) a
  visit ID can poll `GET /api/visit/<id>` indefinitely. A signed, expiring
  token would scope access to a single visit for a limited time window
  without requiring patients to create accounts. Deferred because it adds
  token issuance, expiry, and verification infrastructure that the
  capstone timeline doesn't call for; the UUID4 ID change in this pass
  already makes the ID unguessable, which covers the most realistic risk.
- **CSRF middleware.** The app relies on `SameSite=Lax` cookies and a
  credentialed CORS allowlist rather than CSRF tokens. A dedicated CSRF
  token would add defense-in-depth against cross-site request forgery from
  any future same-site-adjacent surface. Deferred as out of scope for this
  pass; the current allowlist + SameSite combination is a reasonable
  baseline for a single known frontend origin.
- **CAPTCHA on login/check-in.** Rate limiting (added in this pass) blunts
  scripted abuse; a CAPTCHA would add a stronger human-verification layer
  against more determined automated attacks. Deferred because it adds a
  third-party dependency and a UX cost that isn't justified at this scale.
- **Centralized security logging/alerting.** Failed logins, rate-limit hits,
  and validation rejections currently only go to the application log on
  whichever machine is running the process. A centralized log
  aggregator with alerting would let staff notice an attack in real time
  instead of after the fact. Deferred - no infrastructure for this exists
  yet and standing one up is a separate project, not a quick fix.
- **Automated dependency scanning (pip-audit / npm audit) in CI.** There is
  currently no CI pipeline running these checks on every change, so a newly
  disclosed vulnerability in a dependency wouldn't be caught automatically.
  Deferred because there is no CI pipeline set up for this project at all
  yet; adding one is a reasonable follow-up once the capstone is further
  along.
- **Dedicated authz/IDOR/rate-limit test suite.** The fixes in this pass were
  each verified manually with a real, executed test (see above), but there
  is no automated regression suite that would catch a future regression in
  these specific protections. Deferred because building a full test suite is
  a larger, separate effort than fixing the findings themselves; the manual
  verification in this pass is the practical middle ground for the
  remaining timeline.
- **Multi-worker scheduler coordination.** The scheduler guard added in this
  pass correctly prevents duplicate jobs from the Werkzeug dev reloader and
  works correctly for the single-worker gunicorn process defined in the
  current `Procfile`. If the deployment is later scaled to multiple gunicorn
  workers (`-w > 1`), each worker would independently start its own
  scheduler and duplicate the 12-hourly health-feed fetch. Full
  coordination (e.g. a distributed lock, or running the scheduler as a
  separate process outside the web workers) was explicitly out of scope for
  this pass; it only becomes relevant if/when the worker count changes.
