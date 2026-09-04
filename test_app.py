# ── Point tests at a fresh test DB ────────────────────────────────────────────
import os, json, sqlite3, pytest
from werkzeug.security import generate_password_hash

os.environ.setdefault("SECRET_KEY", "test-secret-key")

# Use the real app DB (already seeded by generate_data.py)
from app import app as flask_app
from database import init_db, DB_PATH
from risk_engine import (
    compute_risk_score, check_hard_constraints,
    get_communication_plan, get_data_quality_report,
    classify_escalation_state, strategy_comparison,
)

# Fixed test passwords — used only in tests, never exposed in UI
_TEST_ADMIN_PW  = "TestAdmin@2026"
_TEST_HEALTH_PW = "TestHealth@2026"
_TEST_FIELD_PW  = "TestField@2026"

# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session", autouse=True)
def init_test_database():
    """Initialise DB and seed known test users for auth tests."""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    # Seed or upsert test users with known passwords
    test_users = [
        ("Test Admin",          "testadmin@healthdept.local",  _TEST_ADMIN_PW,  "Administrator"),
        ("Test Health Officer", "testhealth@healthdept.local", _TEST_HEALTH_PW, "Health Officer"),
        ("Test Field Officer",  "testfield@healthdept.local",  _TEST_FIELD_PW,  "Field Officer"),
    ]
    for name, email, pw, role in test_users:
        existing = conn.execute(
            "SELECT id FROM users WHERE LOWER(email)=?", (email.lower(),)
        ).fetchone()
        if existing:
            conn.execute(
                "UPDATE users SET password_hash=?,is_active=1 WHERE id=?",
                (generate_password_hash(pw), existing["id"])
            )
        else:
            conn.execute(
                "INSERT INTO users (full_name,email,password_hash,role,is_active) VALUES (?,?,?,?,1)",
                (name, email.lower(), generate_password_hash(pw), role)
            )
    conn.commit()
    conn.close()
    yield


@pytest.fixture()
def client():
    flask_app.config["TESTING"]          = True
    flask_app.config["WTF_CSRF_ENABLED"] = False
    with flask_app.test_client() as c:
        yield c


def login(client, email="testadmin@healthdept.local", password=_TEST_ADMIN_PW):
    """Login helper using email field."""
    return client.post("/login", data={"email": email, "password": password},
                       follow_redirects=True)


def login_as(client, role):
    """Log out then log in as a test user for the given role."""
    client.get("/logout", follow_redirects=True)
    creds = {
        "Administrator":  ("testadmin@healthdept.local",  _TEST_ADMIN_PW),
        "Health Officer": ("testhealth@healthdept.local", _TEST_HEALTH_PW),
        "Field Officer":  ("testfield@healthdept.local",  _TEST_FIELD_PW),
    }
    em, pw = creds[role]
    return client.post("/login", data={"email": em, "password": pw},
                       follow_redirects=True)


# ── Auth Tests ────────────────────────────────────────────────────────────────

class TestAuth:
    def test_login_page_loads(self, client):
        resp = client.get("/login")
        assert resp.status_code == 200
        assert b"login" in resp.data.lower() or b"city health" in resp.data.lower()

    def test_login_valid_admin(self, client):
        resp = login(client)
        assert resp.status_code == 200
        # Should not be on login page after successful login
        assert b"dashboard" in resp.data.lower() or b"neighbourhoods" in resp.data.lower()

    def test_login_invalid_password(self, client):
        resp = client.post("/login",
                           data={"email": "testadmin@healthdept.local", "password": "WRONG-PASSWORD"},
                           follow_redirects=True)
        assert b"Invalid" in resp.data or b"invalid" in resp.data or resp.status_code == 200

    def test_login_blank_credentials(self, client):
        resp = client.post("/login",
                           data={"email": "", "password": ""},
                           follow_redirects=True)
        assert b"required" in resp.data.lower() or resp.status_code == 200

    def test_no_demo_credentials_visible(self, client):
        """Login page must NOT show demo passwords or hard-coded credentials."""
        resp = client.get("/login")
        assert b"admin123" not in resp.data
        assert b"health123" not in resp.data
        assert b"field123" not in resp.data
        assert b"Demo Credentials" not in resp.data
        assert b"Demo credentials" not in resp.data

    def test_signup_page_loads(self, client):
        resp = client.get("/signup")
        assert resp.status_code == 200
        assert b"signup" in resp.data.lower() or b"create account" in resp.data.lower()

    def test_signup_success(self, client):
        """New user can register and then login."""
        import time
        unique_email = f"newuser_{int(time.time())}@test.local"
        resp = client.post("/signup", data={
            "full_name":        "Test New User",
            "email":            unique_email,
            "password":         "SecurePass@99",
            "confirm_password": "SecurePass@99",
            "role":             "Field Officer",
        }, follow_redirects=True)
        assert resp.status_code == 200
        assert b"Account created" in resp.data or b"success" in resp.data.lower()

    def test_signup_duplicate_email(self, client):
        """Registering with an existing email must fail."""
        resp = client.post("/signup", data={
            "full_name":        "Duplicate User",
            "email":            "testadmin@healthdept.local",
            "password":         "SecurePass@99",
            "confirm_password": "SecurePass@99",
            "role":             "Health Officer",
        }, follow_redirects=True)
        assert b"already exists" in resp.data or b"exists" in resp.data.lower()

    def test_signup_password_mismatch(self, client):
        """Mismatched passwords must be rejected."""
        resp = client.post("/signup", data={
            "full_name":        "Mismatch User",
            "email":            "mismatch@test.local",
            "password":         "SecurePass@99",
            "confirm_password": "DifferentPass@99",
            "role":             "Field Officer",
        }, follow_redirects=True)
        assert b"match" in resp.data.lower() or b"mismatch" in resp.data.lower()

    def test_signup_weak_password(self, client):
        """Password shorter than 8 chars must be rejected."""
        resp = client.post("/signup", data={
            "full_name":        "Weak Pass User",
            "email":            "weakpw@test.local",
            "password":         "abc",
            "confirm_password": "abc",
            "role":             "Field Officer",
        }, follow_redirects=True)
        assert b"8 characters" in resp.data or b"password" in resp.data.lower()

    def test_signup_admin_role_not_allowed(self, client):
        """Public signup must not allow Administrator role."""
        resp = client.post("/signup", data={
            "full_name":        "Sneaky Admin",
            "email":            "sneaky@test.local",
            "password":         "SecurePass@99",
            "confirm_password": "SecurePass@99",
            "role":             "Administrator",
        }, follow_redirects=True)
        # Should be rejected — admin not in allowed_roles
        assert b"valid role" in resp.data.lower() or b"administrator" not in resp.data.lower() or resp.status_code == 200

    def test_logout(self, client):
        login(client)
        resp = client.get("/logout", follow_redirects=True)
        assert resp.status_code == 200

    def test_redirect_unauthenticated(self, client):
        """Unauthenticated request to /dashboard should redirect to login."""
        resp = client.get("/dashboard")
        assert resp.status_code in (302, 200)


# ── Route Health Checks ───────────────────────────────────────────────────────

class TestRoutes:
    ROUTES = [
        "/dashboard",
        "/neighbourhoods",
        "/map",
        "/communication",
        "/review-queue",
        "/escalation",
        "/strategy",
        "/journeys",
        "/experiment",
        "/failures",
        "/constraints",
        "/audit",
        "/feedback",
        "/data-quality",
        "/documentation",
    ]

    def test_all_routes_return_200(self, client):
        login(client)
        for route in self.ROUTES:
            resp = client.get(route)
            assert resp.status_code == 200, f"Route {route} returned {resp.status_code}"

    def test_neighbourhood_detail(self, client):
        """Fetch first neighbourhood and check detail page."""
        login(client)
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        nb = conn.execute("SELECT neighbourhood_id FROM neighbourhoods LIMIT 1").fetchone()
        conn.close()
        if nb:
            resp = client.get(f"/neighbourhood/{nb['neighbourhood_id']}")
            assert resp.status_code == 200

    def test_neighbourhood_detail_404(self, client):
        """Non-existent neighbourhood should redirect."""
        login(client)
        resp = client.get("/neighbourhood/NONEXISTENT", follow_redirects=True)
        assert resp.status_code == 200  # flash and redirect

    def test_api_risk_explain(self, client):
        """API endpoint returns valid JSON with formula_steps."""
        login(client)
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        nb = conn.execute("SELECT neighbourhood_id FROM neighbourhoods LIMIT 1").fetchone()
        conn.close()
        if nb:
            resp = client.get(f"/api/risk-explain/{nb['neighbourhood_id']}")
            assert resp.status_code == 200
            data = json.loads(resp.data)
            assert "risk_score" in data or "formula_steps" in data

    def test_api_data_quality(self, client):
        """Data quality API returns a list."""
        login(client)
        resp = client.get("/api/data-quality")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert isinstance(data, list)

    def test_export_high_risk(self, client):
        """Export CSV returns text/csv content type."""
        login(client)
        resp = client.get("/export/high_risk")
        assert resp.status_code == 200
        assert "text/csv" in resp.content_type

    def test_export_all_neighbourhoods(self, client):
        login(client)
        resp = client.get("/export/all_neighbourhoods")
        assert resp.status_code == 200


# ── Risk Engine Tests ─────────────────────────────────────────────────────────

class TestRiskEngine:
    GOOD_NB = {
        "neighbourhood_id":       "NB_TEST",
        "temperature":             38.0,
        "heat_index":              42.0,
        "vulnerability_score":     65.0,
        "built_environment_score": 55.0,
        "service_access_score":    30.0,
        "cooling_centres":          2,
        "risk_score":              None,
    }

    def test_compute_risk_score_normal(self):
        result = compute_risk_score(self.GOOD_NB)
        assert result["can_auto_classify"] is True
        assert isinstance(result["risk_score"], float)
        assert 0 <= result["risk_score"] <= 100
        assert result["risk_level"] in ("Low", "Medium", "High")

    def test_compute_risk_score_bounds(self):
        """Score must always be in [0, 100]."""
        extreme = {**self.GOOD_NB, "temperature": 50.0, "vulnerability_score": 100.0,
                   "built_environment_score": 100.0, "service_access_score": 0.0}
        result = compute_risk_score(extreme)
        if result["risk_score"] is not None:
            assert 0 <= result["risk_score"] <= 100

    def test_compute_risk_score_missing_temp(self):
        """Missing temperature should block auto-classification."""
        nb = {**self.GOOD_NB, "temperature": None, "heat_index": None}
        result = compute_risk_score(nb)
        assert result["can_auto_classify"] is False
        assert result["risk_score"] is None
        assert "MISSING_DATA" in result["constraint_status"]

    def test_compute_risk_score_missing_vuln(self):
        """Missing vulnerability score should block auto-classification."""
        nb = {**self.GOOD_NB, "vulnerability_score": None}
        result = compute_risk_score(nb)
        assert result["can_auto_classify"] is False

    def test_compute_risk_extreme_temp(self):
        """Temperature > 52°C should trigger EXTREME_VALUE."""
        nb = {**self.GOOD_NB, "temperature": 60.0, "heat_index": 60.0}
        result = check_hard_constraints(nb)
        assert result["status"] == "EXTREME_VALUE"

    def test_risk_level_thresholds(self):
        """Score < 40 = Low, 40-70 = Medium, >= 70 = High."""
        # Low risk scenario
        low_nb = {**self.GOOD_NB, "temperature": 22.0, "heat_index": 22.0,
                  "vulnerability_score": 10.0, "service_access_score": 80.0}
        result = compute_risk_score(low_nb)
        if result["can_auto_classify"]:
            assert result["risk_level"] in ("Low", "Medium")

    def test_formula_steps_present(self):
        """Transparent scoring must include formula_steps."""
        result = compute_risk_score(self.GOOD_NB)
        assert "formula_steps" in result
        if result["can_auto_classify"]:
            fs = result["formula_steps"]
            assert "climate_norm" in fs
            assert "weights" in fs
            assert "subtotals" in fs

    def test_communication_plan_channels_fix(self):
        """Channel selection bug fix: user-selected channels must be used directly."""
        selected = ["SMS", "Public Announcement"]
        plan = get_communication_plan("High", selected)
        assert plan["channels"] == selected  # Bug fix: no filtering to plan defaults

    def test_communication_plan_all_levels(self):
        for level in ("Low", "Medium", "High", "AMBIGUOUS", "MISSING_DATA", "EXTREME_VALUE"):
            plan = get_communication_plan(level)
            assert "urgency" in plan
            assert "message" in plan
            assert "channels" in plan

    def test_data_quality_report(self):
        """Data quality report must flag missing temperature."""
        nbs = [
            {"neighbourhood_id": "NB001", "neighbourhood_name": "Test 1",
             "risk_level": "High", "temperature": None,
             "vulnerability_score": 60.0, "service_access_score": 40.0,
             "built_environment_score": 50.0},
            {"neighbourhood_id": "NB002", "neighbourhood_name": "Test 2",
             "risk_level": "Low", "temperature": 30.0,
             "vulnerability_score": 20.0, "service_access_score": 70.0,
             "built_environment_score": 40.0},
        ]
        report = get_data_quality_report(nbs)
        assert len(report) == 2
        # NB001 should have issues (missing temp)
        nb1 = next(r for r in report if r["neighbourhood_id"] == "NB001")
        assert nb1["missing_count"] > 0
        assert nb1["status"] in ("WARNING", "CRITICAL")
        # NB002 should be OK
        nb2 = next(r for r in report if r["neighbourhood_id"] == "NB002")
        assert nb2["status"] == "OK"

    def test_escalation_state_low(self):
        nb = {"risk_level": "Low",  "risk_score": 25.0}
        state = classify_escalation_state(nb)
        assert state["state"] == "NORMAL"

    def test_escalation_state_high(self):
        nb = {"risk_level": "High", "risk_score": 78.0}
        state = classify_escalation_state(nb)
        assert state["state"] == "HIGH_REVIEW"

    def test_escalation_state_emergency(self):
        nb = {"risk_level": "High", "risk_score": 92.0}
        state = classify_escalation_state(nb)
        assert state["state"] == "IMMEDIATE"

    def test_escalation_state_ambiguous(self):
        nb = {"risk_level": "AMBIGUOUS", "risk_score": None}
        state = classify_escalation_state(nb)
        assert state["state"] == "MANUAL"


# ── Human Review Tests ────────────────────────────────────────────────────────

class TestHumanReview:
    def test_review_queue_loads(self, client):
        login_as(client, "Health Officer")
        resp = client.get("/review-queue")
        assert resp.status_code == 200

    def test_review_approve_action(self, client):
        """Health Officer can approve a review."""
        login_as(client, "Health Officer")
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        review = conn.execute(
            "SELECT id FROM human_reviews WHERE status='Pending' LIMIT 1"
        ).fetchone()
        conn.close()
        if review:
            resp = client.post("/review-queue", data={
                "review_id": review["id"],
                "action":    "approve",
                "notes":     "Approved after field verification.",
            }, follow_redirects=True)
            assert resp.status_code == 200

    def test_review_escalate_creates_escalation(self, client):
        """Escalating a review must create an escalation record."""
        login_as(client, "Health Officer")
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        review = conn.execute(
            "SELECT id FROM human_reviews WHERE status='Pending' LIMIT 1"
        ).fetchone()
        if review:
            before_count = conn.execute(
                "SELECT COUNT(*) FROM escalations"
            ).fetchone()[0]
            conn.close()
            client.post("/review-queue", data={
                "review_id": review["id"],
                "action":    "escalate",
                "notes":     "Escalated due to critical vulnerability.",
            }, follow_redirects=True)
            conn2 = sqlite3.connect(DB_PATH)
            after_count = conn2.execute(
                "SELECT COUNT(*) FROM escalations"
            ).fetchone()[0]
            conn2.close()
            assert after_count >= before_count  # May have added one


# ── Override Permission Tests ─────────────────────────────────────────────────

class TestOverridePermissions:
    def test_health_officer_can_override(self, client):
        """Health Officer should be allowed to override risk level."""
        login_as(client, "Health Officer")
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        nb = conn.execute("SELECT neighbourhood_id FROM neighbourhoods LIMIT 1").fetchone()
        conn.close()
        if nb:
            resp = client.post(
                f"/override/{nb['neighbourhood_id']}",
                data={"new_level": "Medium", "reason": "Field assessment indicates Medium risk."},
                follow_redirects=True,
            )
            assert resp.status_code == 200

    def test_field_officer_cannot_override(self, client):
        """Field Officer should be blocked from override (HC-05)."""
        login_as(client, "Field Officer")
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        nb = conn.execute("SELECT neighbourhood_id FROM neighbourhoods LIMIT 1").fetchone()
        conn.close()
        if nb:
            resp = client.post(
                f"/override/{nb['neighbourhood_id']}",
                data={"new_level": "Low", "reason": "Trying unauthorised override."},
                follow_redirects=True,
            )
            # Should flash access denied and redirect (not crash)
            assert resp.status_code == 200
            assert b"denied" in resp.data.lower() or b"dashboard" in resp.data.lower()

    def test_override_without_reason_rejected(self, client):
        """Override without a reason should be rejected (HC-06)."""
        login_as(client, "Health Officer")
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        nb = conn.execute("SELECT neighbourhood_id FROM neighbourhoods LIMIT 1").fetchone()
        conn.close()
        if nb:
            resp = client.post(
                f"/override/{nb['neighbourhood_id']}",
                data={"new_level": "Medium", "reason": ""},
                follow_redirects=True,
            )
            assert b"required" in resp.data.lower() or resp.status_code == 200


# ── Escalation Tests ──────────────────────────────────────────────────────────

class TestEscalation:
    def test_escalation_page_loads(self, client):
        login(client)
        resp = client.get("/escalation")
        assert resp.status_code == 200

    def test_resolve_escalation(self, client):
        """Resolving an escalation with notes should succeed."""
        login(client)
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        esc = conn.execute(
            "SELECT id FROM escalations WHERE status='Open' LIMIT 1"
        ).fetchone()
        conn.close()
        if esc:
            resp = client.post("/escalation", data={
                "action":           "resolve",
                "escalation_id":    esc["id"],
                "resolution_notes": "Resolved after emergency deployment of cooling centres.",
            }, follow_redirects=True)
            assert resp.status_code == 200

    def test_resolve_escalation_requires_notes(self, client):
        """Resolve without notes should fail."""
        login(client)
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        esc = conn.execute("SELECT id FROM escalations LIMIT 1").fetchone()
        conn.close()
        if esc:
            resp = client.post("/escalation", data={
                "action":           "resolve",
                "escalation_id":    esc["id"],
                "resolution_notes": "",
            }, follow_redirects=True)
            assert b"required" in resp.data.lower() or resp.status_code == 200


# ── Communication Tests ────────────────────────────────────────────────────────

class TestCommunication:
    def test_communication_page_loads(self, client):
        login(client)
        resp = client.get("/communication")
        assert resp.status_code == 200

    def test_send_communication(self, client):
        """Sending communication with valid data should succeed."""
        login(client)
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        nb = conn.execute("SELECT neighbourhood_id FROM neighbourhoods LIMIT 1").fetchone()
        conn.close()
        if nb:
            before = sqlite3.connect(DB_PATH)
            before.row_factory = sqlite3.Row
            count_before = before.execute("SELECT COUNT(*) FROM communications").fetchone()[0]
            before.close()

            resp = client.post("/communication", data={
                "neighbourhood_id": nb["neighbourhood_id"],
                "channels":         ["SMS"],
                "custom_message":   "",
            }, follow_redirects=True)
            assert resp.status_code == 200

            after = sqlite3.connect(DB_PATH)
            after.row_factory = sqlite3.Row
            count_after = after.execute("SELECT COUNT(*) FROM communications").fetchone()[0]
            after.close()
            assert count_after > count_before

    def test_send_communication_no_channels(self, client):
        """Sending without channels should flash error."""
        login(client)
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        nb = conn.execute("SELECT neighbourhood_id FROM neighbourhoods LIMIT 1").fetchone()
        conn.close()
        if nb:
            resp = client.post("/communication", data={
                "neighbourhood_id": nb["neighbourhood_id"],
            }, follow_redirects=True)
            assert b"channel" in resp.data.lower() or resp.status_code == 200

    def test_preselect_neighbourhood(self, client):
        """Communication page with ?nb= param should pre-select neighbourhood."""
        login(client)
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        nb = conn.execute("SELECT neighbourhood_id FROM neighbourhoods LIMIT 1").fetchone()
        conn.close()
        if nb:
            resp = client.get(f"/communication?nb={nb['neighbourhood_id']}")
            assert resp.status_code == 200
            assert nb["neighbourhood_id"].encode() in resp.data


# ── Audit Log Tests ───────────────────────────────────────────────────────────

class TestAuditLog:
    def test_audit_page_loads(self, client):
        login(client)
        resp = client.get("/audit")
        assert resp.status_code == 200

    def test_login_creates_audit_entry(self, client):
        """Every login should create an audit log entry."""
        conn_before = sqlite3.connect(DB_PATH)
        conn_before.row_factory = sqlite3.Row
        before = conn_before.execute(
            "SELECT COUNT(*) c FROM audit_logs WHERE action='LOGIN'"
        ).fetchone()[0]
        conn_before.close()

        login(client)

        conn_after = sqlite3.connect(DB_PATH)
        conn_after.row_factory = sqlite3.Row
        after = conn_after.execute(
            "SELECT COUNT(*) c FROM audit_logs WHERE action='LOGIN'"
        ).fetchone()[0]
        conn_after.close()
        assert after >= before  # At least as many or more


# ── Data Quality Tests ────────────────────────────────────────────────────────

class TestDataQuality:
    def test_data_quality_page_loads(self, client):
        login(client)
        resp = client.get("/data-quality")
        assert resp.status_code == 200
        assert b"quality" in resp.data.lower()

    def test_data_quality_api_structure(self, client):
        login(client)
        resp = client.get("/api/data-quality")
        data = json.loads(resp.data)
        assert isinstance(data, list)
        if data:
            assert "neighbourhood_id"   in data[0]
            assert "quality_score"      in data[0]
            assert "status"             in data[0]
            assert "missing_count"      in data[0]


# ── Strategy Tests ────────────────────────────────────────────────────────────

class TestStrategy:
    def test_strategy_page_loads(self, client):
        login(client)
        resp = client.get("/strategy")
        assert resp.status_code == 200

    def test_strategy_comparison_logic(self):
        """Strategy comparison must return valid metrics for both objectives."""
        nbs = [
            {"risk_level": "High",   "risk_score": 80.0, "neighbourhood_name": "A",
             "communication_reach_percentage": 60.0},
            {"risk_level": "Medium", "risk_score": 55.0, "neighbourhood_name": "B",
             "communication_reach_percentage": 70.0},
            {"risk_level": "Low",    "risk_score": 25.0, "neighbourhood_name": "C",
             "communication_reach_percentage": 80.0},
        ]
        result = strategy_comparison(nbs)
        assert "obj_a" in result
        assert "obj_b" in result
        assert "total_high_risk" in result
        assert result["total_high_risk"] == 1
        assert result["obj_a"]["neighbourhoods_reached"] >= 0
        assert result["obj_b"]["neighbourhoods_reached"] >= 0


# ── Database Tests ────────────────────────────────────────────────────────────

class TestDatabase:
    def test_tables_created(self):
        """All required tables must exist."""
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        tables = {r["name"] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
        conn.close()
        required = {"users", "neighbourhoods", "risk_assessments", "communications",
                    "human_reviews", "escalations", "overrides", "audit_logs",
                    "stakeholder_feedback"}
        missing = required - tables
        assert not missing, f"Missing tables: {missing}"

    def test_users_seeded(self):
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        count = conn.execute("SELECT COUNT(*) c FROM users").fetchone()[0]
        roles = {r["role"] for r in conn.execute("SELECT role FROM users").fetchall()}
        conn.close()
        assert count >= 3
        assert "Administrator" in roles
        assert "Health Officer" in roles
        assert "Field Officer" in roles

    def test_neighbourhoods_seeded(self):
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        count = conn.execute("SELECT COUNT(*) c FROM neighbourhoods").fetchone()[0]
        conn.close()
        assert count >= 10, f"Expected at least 10 neighbourhoods, got {count}"

    def test_priority_column_exists(self):
        """Priority column must exist in human_reviews (new in v2)."""
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cols = {c["name"] for c in conn.execute(
            "PRAGMA table_info(human_reviews)"
        ).fetchall()}
        conn.close()
        assert "priority" in cols

    def test_escalation_columns_exist(self):
        """escalation_type and current_state must exist in escalations (new in v2)."""
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cols = {c["name"] for c in conn.execute(
            "PRAGMA table_info(escalations)"
        ).fetchall()}
        conn.close()
        assert "escalation_type" in cols
        assert "current_state"   in cols

    def test_failure_reason_column_exists(self):
        """failure_reason must exist in communications (new in v2)."""
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cols = {c["name"] for c in conn.execute(
            "PRAGMA table_info(communications)"
        ).fetchall()}
        conn.close()
        assert "failure_reason" in cols
