"""
database.py  v2
Initialises the SQLite database, creates all tables, and seeds demo data.
New in v2:
  - priority column in human_reviews
  - escalation_type / current_state in escalations
  - failure_reason in communications
  - data_quality_flag in neighbourhoods
  - richer seed data with priorities and escalation types
"""

import sqlite3
import os
import csv
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash

DB_PATH  = os.path.join(os.path.dirname(__file__), "heat_risk.db")
CSV_PATH = os.path.join(os.path.dirname(__file__), "neighbourhood_heat_risk.csv")


def get_db():
    """Return a database connection with row_factory set."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    """Create all tables and seed initial data."""
    conn = get_db()
    cur  = conn.cursor()

    # ── Schema ────────────────────────────────────────────────────────────────
    cur.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        full_name     TEXT NOT NULL,
        email         TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role          TEXT NOT NULL CHECK(role IN ('Administrator','Health Officer','Field Officer')),
        username      TEXT,
        is_active     INTEGER DEFAULT 1,
        created_at    TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS neighbourhoods (
        neighbourhood_id               TEXT PRIMARY KEY,
        neighbourhood_name             TEXT NOT NULL,
        latitude                       REAL,
        longitude                      REAL,
        temperature                    REAL,
        humidity                       REAL,
        heat_index                     REAL,
        population                     INTEGER,
        elderly_percentage             REAL,
        child_percentage               REAL,
        low_income_percentage          REAL,
        population_density             INTEGER,
        green_space_percentage         REAL,
        building_density               REAL,
        healthcare_facilities          INTEGER,
        nearest_hospital_distance      REAL,
        cooling_centres                INTEGER,
        public_transport_access        INTEGER,
        service_access_score           REAL,
        vulnerability_score            REAL,
        built_environment_score        REAL,
        infectious_disease_cases       INTEGER,
        previous_heat_incidents        INTEGER,
        communication_reach_percentage REAL,
        risk_score                     REAL,
        risk_level                     TEXT,
        data_quality_flag              TEXT DEFAULT 'OK',
        data_last_updated              TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS risk_assessments (
        id                   INTEGER PRIMARY KEY AUTOINCREMENT,
        neighbourhood_id     TEXT NOT NULL,
        assessed_at          TEXT DEFAULT (datetime('now')),
        risk_score           REAL,
        risk_level           TEXT,
        climate_contribution REAL,
        vuln_contribution    REAL,
        built_contribution   REAL,
        service_contribution REAL,
        missing_data_flag    INTEGER DEFAULT 0,
        ambiguous_flag       INTEGER DEFAULT 0,
        review_required      INTEGER DEFAULT 0,
        notes                TEXT,
        FOREIGN KEY (neighbourhood_id) REFERENCES neighbourhoods(neighbourhood_id)
    );

    CREATE TABLE IF NOT EXISTS communications (
        id               INTEGER PRIMARY KEY AUTOINCREMENT,
        neighbourhood_id TEXT NOT NULL,
        channel          TEXT NOT NULL,
        message_type     TEXT,
        message_text     TEXT,
        status           TEXT DEFAULT 'Planned',
        sent_at          TEXT,
        sent_by          INTEGER,
        failure_reason   TEXT,
        created_at       TEXT DEFAULT (datetime('now')),
        FOREIGN KEY (neighbourhood_id) REFERENCES neighbourhoods(neighbourhood_id),
        FOREIGN KEY (sent_by) REFERENCES users(id)
    );

    CREATE TABLE IF NOT EXISTS human_reviews (
        id                 INTEGER PRIMARY KEY AUTOINCREMENT,
        neighbourhood_id   TEXT NOT NULL,
        risk_score         REAL,
        risk_level         TEXT,
        reason             TEXT,
        recommended_action TEXT,
        priority           TEXT DEFAULT 'Normal',
        assigned_to        INTEGER,
        status             TEXT DEFAULT 'Pending',
        review_notes       TEXT,
        created_at         TEXT DEFAULT (datetime('now')),
        reviewed_at        TEXT,
        FOREIGN KEY (neighbourhood_id) REFERENCES neighbourhoods(neighbourhood_id),
        FOREIGN KEY (assigned_to) REFERENCES users(id)
    );

    CREATE TABLE IF NOT EXISTS escalations (
        id               INTEGER PRIMARY KEY AUTOINCREMENT,
        neighbourhood_id TEXT NOT NULL,
        review_id        INTEGER,
        escalation_type  TEXT DEFAULT 'High Risk',
        current_state    TEXT DEFAULT 'Open',
        level            TEXT,
        reason           TEXT,
        escalated_by     INTEGER,
        assigned_to      INTEGER,
        status           TEXT DEFAULT 'Open',
        resolution_notes TEXT,
        created_at       TEXT DEFAULT (datetime('now')),
        resolved_at      TEXT,
        FOREIGN KEY (neighbourhood_id) REFERENCES neighbourhoods(neighbourhood_id),
        FOREIGN KEY (escalated_by) REFERENCES users(id)
    );

    CREATE TABLE IF NOT EXISTS overrides (
        id               INTEGER PRIMARY KEY AUTOINCREMENT,
        neighbourhood_id TEXT NOT NULL,
        user_id          INTEGER NOT NULL,
        original_level   TEXT,
        new_level        TEXT,
        reason           TEXT NOT NULL,
        overridden_at    TEXT DEFAULT (datetime('now')),
        FOREIGN KEY (neighbourhood_id) REFERENCES neighbourhoods(neighbourhood_id),
        FOREIGN KEY (user_id) REFERENCES users(id)
    );

    CREATE TABLE IF NOT EXISTS audit_logs (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id     INTEGER,
        username    TEXT,
        action      TEXT NOT NULL,
        entity_type TEXT,
        entity_id   TEXT,
        detail      TEXT,
        ip_address  TEXT,
        logged_at   TEXT DEFAULT (datetime('now')),
        FOREIGN KEY (user_id) REFERENCES users(id)
    );

    CREATE TABLE IF NOT EXISTS stakeholder_feedback (
        id                     INTEGER PRIMARY KEY AUTOINCREMENT,
        respondent_role        TEXT,
        respondent_name        TEXT,
        q_risk_understandable  INTEGER,
        q_escalation_clear     INTEGER,
        q_actions_useful       INTEGER,
        q_dashboard_easy       INTEGER,
        improvement_notes      TEXT,
        submitted_at           TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS risk_snapshots (
        id                   INTEGER PRIMARY KEY AUTOINCREMENT,
        neighbourhood_id     TEXT NOT NULL,
        risk_score           REAL,
        risk_level           TEXT,
        temperature          REAL,
        heat_index           REAL,
        vulnerability_score  REAL,
        service_access_score REAL,
        notes                TEXT,
        recorded_by          INTEGER,
        recorded_at          TEXT DEFAULT (datetime('now')),
        FOREIGN KEY (neighbourhood_id) REFERENCES neighbourhoods(neighbourhood_id),
        FOREIGN KEY (recorded_by) REFERENCES users(id)
    );

    -- Performance Indexes
    CREATE INDEX IF NOT EXISTS idx_nb_risk_level ON neighbourhoods(risk_level);
    CREATE INDEX IF NOT EXISTS idx_nb_risk_score ON neighbourhoods(risk_score);
    CREATE INDEX IF NOT EXISTS idx_hr_status ON human_reviews(status);
    CREATE INDEX IF NOT EXISTS idx_esc_status ON escalations(status);
    CREATE INDEX IF NOT EXISTS idx_comm_status ON communications(status);
    CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_logs(action);
    CREATE INDEX IF NOT EXISTS idx_audit_user ON audit_logs(user_id);
    CREATE INDEX IF NOT EXISTS idx_snapshots_nb ON risk_snapshots(neighbourhood_id);
    """)
    conn.commit()

    # ── Migrate: safe add columns for email-based auth & v3 features ────────
    _safe_add_column(cur, "users",         "is_active",        "INTEGER DEFAULT 1")
    _safe_add_column(cur, "users",         "last_active",      "TEXT")
    _safe_add_column(cur, "human_reviews",  "priority",         "TEXT DEFAULT 'Normal'")
    _safe_add_column(cur, "escalations",    "escalation_type",  "TEXT DEFAULT 'High Risk'")
    _safe_add_column(cur, "escalations",    "current_state",    "TEXT DEFAULT 'Open'")
    _safe_add_column(cur, "escalations",    "resolution_notes", "TEXT")
    _safe_add_column(cur, "communications", "failure_reason",   "TEXT")
    _safe_add_column(cur, "communications", "target_audience",  "TEXT")
    _safe_add_column(cur, "communications", "priority",         "TEXT DEFAULT 'Standard'")
    _safe_add_column(cur, "neighbourhoods", "data_quality_flag","TEXT DEFAULT 'OK'")
    conn.commit()

    # ── Seed: create initial admin only if NO users exist at all ───────────────
    import secrets
    existing = cur.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    if existing == 0:
        init_pw = secrets.token_urlsafe(12)
        cur.execute(
            "INSERT INTO users (full_name,email,password_hash,role,is_active) VALUES (?,?,?,?,1)",
            ("System Administrator", "admin@healthdept.local",
             generate_password_hash(init_pw), "Administrator")
        )
        conn.commit()
        print("=" * 60)
        print("[FIRST RUN] Initial administrator account created:")
        print(f"  Email   : admin@healthdept.local")
        print(f"  Password: {init_pw}")
        print("  Change this password after first login.")
        print("=" * 60)


    # ── Load CSV into neighbourhoods table ────────────────────────────────────
    if os.path.exists(CSV_PATH):
        with open(CSV_PATH, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                cur.execute("""
                INSERT OR REPLACE INTO neighbourhoods (
                    neighbourhood_id, neighbourhood_name, latitude, longitude,
                    temperature, humidity, heat_index,
                    population, elderly_percentage, child_percentage,
                    low_income_percentage, population_density,
                    green_space_percentage, building_density,
                    healthcare_facilities, nearest_hospital_distance,
                    cooling_centres, public_transport_access,
                    service_access_score, vulnerability_score, built_environment_score,
                    infectious_disease_cases, previous_heat_incidents,
                    communication_reach_percentage, risk_score, risk_level, data_quality_flag
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """, (
                    row["neighbourhood_id"], row["neighbourhood_name"],
                    _sf(row.get("latitude")),   _sf(row.get("longitude")),
                    _sf(row.get("temperature")), _sf(row.get("humidity")),
                    _sf(row.get("heat_index")),
                    _si(row.get("population")), _sf(row.get("elderly_percentage")),
                    _sf(row.get("child_percentage")), _sf(row.get("low_income_percentage")),
                    _si(row.get("population_density")),
                    _sf(row.get("green_space_percentage")), _sf(row.get("building_density")),
                    _si(row.get("healthcare_facilities")), _sf(row.get("nearest_hospital_distance")),
                    _si(row.get("cooling_centres")), _si(row.get("public_transport_access")),
                    _sf(row.get("service_access_score")), _sf(row.get("vulnerability_score")),
                    _sf(row.get("built_environment_score")),
                    _si(row.get("infectious_disease_cases")), _si(row.get("previous_heat_incidents")),
                    _sf(row.get("communication_reach_percentage")),
                    _sf(row.get("risk_score")), row.get("risk_level","AMBIGUOUS"),
                    _quality_flag(row),
                ))
    conn.commit()

    # ── Seed risk assessments ─────────────────────────────────────────────────
    rows = cur.execute("SELECT * FROM neighbourhoods").fetchall()
    for nb in rows:
        temp    = nb["temperature"] or 0
        clim_c  = round((min(float(temp), 50) / 50) * 0.35 * 100, 1) if temp else 0
        vuln_c  = round((nb["vulnerability_score"]    or 0) / 100 * 0.30 * 100, 1)
        built_c = round((nb["built_environment_score"] or 0) / 100 * 0.20 * 100, 1)
        serv_c  = round((1 - (nb["service_access_score"] or 50) / 100) * 0.15 * 100, 1)
        missing = 1 if nb["temperature"] is None else 0
        ambig   = 1 if nb["risk_level"] == "AMBIGUOUS" else 0
        review  = 1 if nb["risk_level"] in ("High","AMBIGUOUS") else 0
        cur.execute("""
        INSERT OR IGNORE INTO risk_assessments
        (neighbourhood_id, risk_score, risk_level,
         climate_contribution, vuln_contribution, built_contribution, service_contribution,
         missing_data_flag, ambiguous_flag, review_required)
        SELECT ?,?,?,?,?,?,?,?,?,?
        WHERE NOT EXISTS (SELECT 1 FROM risk_assessments WHERE neighbourhood_id=?)
        """, (nb["neighbourhood_id"], nb["risk_score"], nb["risk_level"],
              clim_c, vuln_c, built_c, serv_c, missing, ambig, review,
              nb["neighbourhood_id"]))

    # ── Seed human reviews with priority ─────────────────────────────────────
    _ho_row = cur.execute(
        "SELECT id FROM users WHERE role='Health Officer' LIMIT 1"
    ).fetchone()
    if _ho_row is None:
        _ho_row = cur.execute("SELECT id FROM users LIMIT 1").fetchone()
    health_officer_id = _ho_row["id"] if _ho_row else 1

    high_nbs = cur.execute(
        "SELECT neighbourhood_id, risk_score, risk_level FROM neighbourhoods "
        "WHERE risk_level IN ('High','AMBIGUOUS') ORDER BY risk_score DESC NULLS LAST"
    ).fetchall()
    statuses   = ["Pending","In Review","Approved","Escalated","Pending","Info Requested","Pending"]
    priorities = {
        "High":      ["Critical","Critical","High","High","Normal","Normal","Critical"],
        "AMBIGUOUS": ["High","Normal","Normal","High","Normal","Normal","Normal"],
    }
    reasons = {
        "High":      "Neighbourhood scored High risk — mandatory Health Officer review required before any communication.",
        "AMBIGUOUS": "Conflicting or missing indicators detected — manual data validation and review required.",
    }
    actions = {
        "High":      "Deploy urgent communication and dispatch field outreach team within 24 hours.",
        "AMBIGUOUS": "Gather additional field data, validate indicators, and reassess risk level.",
    }
    for i, nb in enumerate(high_nbs):
        lvl      = nb["risk_level"]
        priority = priorities.get(lvl, ["Normal"]*7)[i % 7]
        status   = statuses[i % len(statuses)]
        cur.execute("""
        INSERT OR IGNORE INTO human_reviews
        (neighbourhood_id, risk_score, risk_level, reason, recommended_action, priority, assigned_to, status)
        SELECT ?,?,?,?,?,?,?,?
        WHERE NOT EXISTS (SELECT 1 FROM human_reviews WHERE neighbourhood_id=?)
        """, (nb["neighbourhood_id"], nb["risk_score"], lvl,
              reasons.get(lvl,"Review required."),
              actions.get(lvl,"Assess and act accordingly."),
              priority, health_officer_id, status,
              nb["neighbourhood_id"]))

    # ── Seed escalations ──────────────────────────────────────────────────────
    admin_id = cur.execute("SELECT id FROM users WHERE role='Administrator' LIMIT 1").fetchone()["id"]
    esc_nbs  = cur.execute(
        "SELECT neighbourhood_id, risk_score, risk_level FROM neighbourhoods "
        "WHERE risk_level='High' ORDER BY risk_score DESC NULLS LAST LIMIT 2"
    ).fetchall()
    esc_types  = ["Immediate Escalation","High Officer Review"]
    esc_states = ["Open","Under Review"]
    for i, nb in enumerate(esc_nbs):
        cur.execute("""
        INSERT OR IGNORE INTO escalations
        (neighbourhood_id, escalation_type, current_state, level, reason, escalated_by, assigned_to, status)
        SELECT ?,?,?,?,?,?,?,?
        WHERE NOT EXISTS (SELECT 1 FROM escalations WHERE neighbourhood_id=?)
        """, (nb["neighbourhood_id"],
              esc_types[i % len(esc_types)],
              esc_states[i % len(esc_states)],
              "High Risk Escalation",
              "High-risk neighbourhood requiring immediate administrator review and response coordination.",
              health_officer_id, admin_id, "Open",
              nb["neighbourhood_id"]))

    # ── Seed communications ────────────────────────────────────────────────────
    comm_samples = [
        ("NB001","SMS","General Advisory",
         "Heat safety tips for Ashfield. Stay hydrated, avoid peak sun 10am–3pm. Cooling centres open.","Sent"),
        ("NB002","Local Health Worker Outreach","Preventive Communication",
         "Targeted heat monitoring for Bankstown. Field team check-in scheduled.","Sent"),
        ("NB003","Public Announcement","Urgent Advisory",
         "URGENT: Blacktown at HIGH heat risk. Cooling centres open 24/7 at Town Hall.","Sent"),
        ("NB004","Social Media Advisory","General Advisory",
         "Stay cool this summer! Check our website for Bondi cooling centre locations.","Planned"),
        ("NB005","SMS","Urgent Advisory",
         "HEAT ALERT: Your neighbourhood requires immediate precautions. Call 1800-HEALTH.","Sent"),
        ("NB006","Community Centre Notice","Targeted Prevention",
         "Elevated heat risk in your area. Visit community cooling centre 9am–6pm daily.","Failed"),
    ]
    for nb_id, channel, mtype, msg, status in comm_samples:
        # Only insert if neighbourhood exists
        exists = cur.execute("SELECT 1 FROM neighbourhoods WHERE neighbourhood_id=?", (nb_id,)).fetchone()
        if exists:
            failure_reason = "Communication centre system offline" if status == "Failed" else None
            cur.execute("""
            INSERT OR IGNORE INTO communications
            (neighbourhood_id, channel, message_type, message_text, status, sent_at, sent_by, failure_reason)
            SELECT ?,?,?,?,?,datetime('now','-1 day'),1,?
            WHERE NOT EXISTS (
                SELECT 1 FROM communications WHERE neighbourhood_id=? AND channel=?
            )
            """, (nb_id, channel, mtype, msg, status, failure_reason, nb_id, channel))

    # ── Seed audit log ─────────────────────────────────────────────────────────
    audit_entries = [
        (1,"admin",          "LOGIN",               "user",          "1",    "Administrator logged in"),
        (2,"health_officer", "RISK_OVERRIDE",        "neighbourhood", "NB003","Override: Medium → High | Reason: Elderly cluster detected"),
        (2,"health_officer", "REVIEW_APPROVE",       "human_review",  "3",   "Review approved for NB003. Urgent comms dispatched."),
        (1,"admin",          "COMMUNICATION_SENT",   "communication", "3",   "Public announcement sent to Blacktown"),
        (1,"admin",          "ESCALATION_CREATED",   "escalation",    "1",   "Immediate escalation created for highest-risk area"),
        (2,"health_officer", "LOGIN",                "user",          "2",   "Health Officer logged in"),
        (3,"field_officer",  "LOGIN",                "user",          "3",   "Field Officer logged in"),
    ]
    for uid, uname, action, etype, eid, detail in audit_entries:
        cur.execute("""
        INSERT OR IGNORE INTO audit_logs
        (user_id, username, action, entity_type, entity_id, detail)
        SELECT ?,?,?,?,?,?
        WHERE NOT EXISTS (
            SELECT 1 FROM audit_logs WHERE username=? AND action=? AND entity_id=?
        )
        """, (uid, uname, action, etype, eid, detail, uname, action, eid))

    # ── Seed stakeholder feedback ──────────────────────────────────────────────
    feedback_entries = [
        ("Health Officer","Dr. Sarah Chen",       5,5,5,4,"Useful for rapid triage. Would like mobile alerts integrated."),
        ("Field Officer","Officer Tom Blake",      4,4,5,5,"Map view excellent. Risk explanation helps brief community leaders."),
        ("Public Health Analyst","Prof. Linda Wu", 5,3,4,4,"Escalation logic strong. Suggest historical trend lines."),
        ("Health Officer","Dr. Priya Nair",        4,5,5,5,"Override audit trail gives us accountability. Great for reporting."),
    ]
    for role, name, q1, q2, q3, q4, notes in feedback_entries:
        cur.execute("""
        INSERT OR IGNORE INTO stakeholder_feedback
        (respondent_role, respondent_name,
         q_risk_understandable, q_escalation_clear, q_actions_useful, q_dashboard_easy, improvement_notes)
        SELECT ?,?,?,?,?,?,?
        WHERE NOT EXISTS (SELECT 1 FROM stakeholder_feedback WHERE respondent_name=?)
        """, (role, name, q1, q2, q3, q4, notes, name))

    conn.commit()
    conn.close()
    print("[OK] Database v2 initialised at", DB_PATH)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _safe_add_column(cur, table, col, definition):
    """Add a column to a table if it does not already exist."""
    try:
        cur.execute(f"ALTER TABLE {table} ADD COLUMN {col} {definition}")
    except Exception:
        pass  # Column already exists


def _sf(v):
    """Safe float conversion."""
    try:
        return float(v) if v not in (None,"","nan","NaN") else None
    except Exception:
        return None


def _si(v):
    """Safe int conversion."""
    try:
        return int(float(v)) if v not in (None,"","nan","NaN") else None
    except Exception:
        return None


def _quality_flag(row):
    """Assess data quality for a CSV row."""
    if _sf(row.get("temperature")) is None:
        return "MISSING_TEMPERATURE"
    if _sf(row.get("vulnerability_score")) is None:
        return "MISSING_VULNERABILITY"
    temp = _sf(row.get("temperature"))
    if temp and temp > 52:
        return "EXTREME_VALUE"
    return "OK"


def log_audit(user_id, username, action, entity_type=None,
              entity_id=None, detail=None, ip=None):
    """Write to audit_logs from any route."""
    conn = get_db()
    conn.execute("""
        INSERT INTO audit_logs
        (user_id, username, action, entity_type, entity_id, detail, ip_address)
        VALUES (?,?,?,?,?,?,?)
    """, (user_id, username, action, entity_type, entity_id, detail, ip))
    conn.commit()
    conn.close()


def create_snapshot(neighbourhood_id, user_id=None, notes=None):
    """Save an immutable historical snapshot of current neighbourhood risk metrics."""
    conn = get_db()
    nb = conn.execute(
        "SELECT * FROM neighbourhoods WHERE neighbourhood_id=?", (neighbourhood_id,)
    ).fetchone()
    if not nb:
        conn.close()
        return None
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO risk_snapshots
        (neighbourhood_id, risk_score, risk_level, temperature, heat_index,
         vulnerability_score, service_access_score, notes, recorded_by)
        VALUES (?,?,?,?,?,?,?,?,?)
    """, (
        neighbourhood_id, nb["risk_score"], nb["risk_level"],
        nb["temperature"], nb["heat_index"], nb["vulnerability_score"],
        nb["service_access_score"], notes or "Manual health surveillance observation",
        user_id
    ))
    snap_id = cur.lastrowid
    conn.commit()
    conn.close()
    return snap_id


def get_snapshots(neighbourhood_id):
    """Retrieve historical snapshots for a given neighbourhood."""
    conn = get_db()
    rows = conn.execute("""
        SELECT rs.*, u.full_name AS recorder_name
        FROM risk_snapshots rs
        LEFT JOIN users u ON rs.recorded_by = u.id
        WHERE rs.neighbourhood_id=?
        ORDER BY rs.recorded_at DESC
    """, (neighbourhood_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_operational_alerts():
    """
    Compute operational alerts directly from live SQLite database state.
    Returns: critical_nbs, pending_reviews, open_escalations, data_issues, failed_comms.
    """
    conn = get_db()
    critical_nbs = [dict(r) for r in conn.execute(
        "SELECT neighbourhood_id, neighbourhood_name, risk_score, risk_level, temperature "
        "FROM neighbourhoods WHERE risk_level='High' OR risk_score >= 80 "
        "ORDER BY risk_score DESC NULLS LAST LIMIT 5"
    ).fetchall()]

    pending_reviews = [dict(r) for r in conn.execute(
        "SELECT hr.*, n.neighbourhood_name FROM human_reviews hr "
        "JOIN neighbourhoods n ON hr.neighbourhood_id=n.neighbourhood_id "
        "WHERE hr.status='Pending' ORDER BY hr.created_at DESC LIMIT 5"
    ).fetchall()]

    open_escalations = [dict(r) for r in conn.execute(
        "SELECT e.*, n.neighbourhood_name FROM escalations e "
        "JOIN neighbourhoods n ON e.neighbourhood_id=n.neighbourhood_id "
        "WHERE e.status='Open' ORDER BY e.created_at DESC LIMIT 5"
    ).fetchall()]

    data_issues = [dict(r) for r in conn.execute(
        "SELECT neighbourhood_id, neighbourhood_name, risk_level, data_quality_flag "
        "FROM neighbourhoods "
        "WHERE data_quality_flag != 'OK' OR risk_level IN ('AMBIGUOUS','MISSING_DATA','EXTREME_VALUE') "
        "LIMIT 5"
    ).fetchall()]

    failed_comms = [dict(r) for r in conn.execute(
        "SELECT c.*, n.neighbourhood_name FROM communications c "
        "JOIN neighbourhoods n ON c.neighbourhood_id=n.neighbourhood_id "
        "WHERE c.status='Failed' ORDER BY c.created_at DESC LIMIT 5"
    ).fetchall()]

    conn.close()
    return {
        "critical_nbs": critical_nbs,
        "critical_count": len(critical_nbs),
        "pending_reviews": pending_reviews,
        "pending_reviews_count": len(pending_reviews),
        "open_escalations": open_escalations,
        "open_escalations_count": len(open_escalations),
        "data_issues": data_issues,
        "data_issues_count": len(data_issues),
        "failed_comms": failed_comms,
        "failed_comms_count": len(failed_comms),
    }


def get_priority_actions():
    """
    Automatically generate prioritized, action-oriented recommendations from database state.
    """
    conn = get_db()
    # 1. Pending reviews count
    rev_cnt = conn.execute("SELECT COUNT(*) c FROM human_reviews WHERE status='Pending'").fetchone()["c"]

    # 2. High-risk areas without any communication yet
    uncontacted_high = [dict(r) for r in conn.execute("""
        SELECT n.neighbourhood_id, n.neighbourhood_name, n.risk_score
        FROM neighbourhoods n
        WHERE n.risk_level = 'High'
        AND NOT EXISTS (
            SELECT 1 FROM communications c
            WHERE c.neighbourhood_id = n.neighbourhood_id AND c.status = 'Sent'
        )
        ORDER BY n.risk_score DESC NULLS LAST
    """).fetchall()]

    # 3. Unresolved escalations
    open_esc_cnt = conn.execute("SELECT COUNT(*) c FROM escalations WHERE status='Open'").fetchone()["c"]

    # 4. Data-quality or ambiguous cases
    dq_cnt = conn.execute("""
        SELECT COUNT(*) c FROM neighbourhoods
        WHERE data_quality_flag != 'OK'
           OR risk_level IN ('AMBIGUOUS','MISSING_DATA','EXTREME_VALUE')
    """).fetchone()["c"]

    # 5. Failed communications
    failed_cnt = conn.execute("SELECT COUNT(*) c FROM communications WHERE status='Failed'").fetchone()["c"]
    conn.close()

    actions = []
    if rev_cnt > 0:
        actions.append({
            "type": "review",
            "title": f"{rev_cnt} neighbourhood{'s' if rev_cnt != 1 else ''} require human review",
            "description": "High-risk or ambiguous cases require Health Officer or Admin assessment.",
            "link": "/review-queue",
            "badge": "Mandatory",
            "urgency": "danger" if rev_cnt >= 3 else "warning",
            "icon": "fa-user-check"
        })
    if uncontacted_high:
        actions.append({
            "type": "communication",
            "title": f"{len(uncontacted_high)} high-risk area{'s' if len(uncontacted_high) != 1 else ''} require communication",
            "description": f"Targeted heat safety outreach needed for: {', '.join(h['neighbourhood_name'] for h in uncontacted_high[:3])}.",
            "link": f"/communication?nb={uncontacted_high[0]['neighbourhood_id']}",
            "badge": "Action Needed",
            "urgency": "danger",
            "icon": "fa-bullhorn"
        })
    if open_esc_cnt > 0:
        actions.append({
            "type": "escalation",
            "title": f"{open_esc_cnt} escalation{' is' if open_esc_cnt == 1 else 's are'} unresolved",
            "description": "Immediate intervention cases awaiting officer response coordination.",
            "link": "/escalation",
            "badge": "Urgent",
            "urgency": "danger",
            "icon": "fa-exclamation-triangle"
        })
    if dq_cnt > 0:
        actions.append({
            "type": "data_quality",
            "title": f"{dq_cnt} neighbourhood{'s have' if dq_cnt != 1 else ' has'} data-quality issues",
            "description": "Missing temperatures or conflicting indicators block automated triage.",
            "link": "/data-quality",
            "badge": "Data Quality",
            "urgency": "warning",
            "icon": "fa-clipboard-list"
        })
    if failed_cnt > 0:
        actions.append({
            "type": "failed_comms",
            "title": f"{failed_cnt} advisory delivery failure{'s' if failed_cnt != 1 else ''} reported",
            "description": "Advisories that encountered system or channel delivery issues.",
            "link": "/communication",
            "badge": "Delivery Alert",
            "urgency": "danger",
            "icon": "fa-satellite-dish"
        })

    return actions

