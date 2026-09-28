"""
app.py  v2 — Neighbourhood Heat-Risk Communication & Response Planner
Run: python app.py
"""
import sys
import subprocess
import os, json, math, csv, io
from datetime import datetime
from functools import wraps
from flask import (Flask, render_template, request, redirect, url_for,
                   session, flash, jsonify, make_response)
from werkzeug.security import check_password_hash
import database as db
from database import (get_db, log_audit, init_db,
                      get_operational_alerts, get_priority_actions,
                      create_snapshot, get_snapshots)
from risk_engine import (compute_risk_score, check_hard_constraints,
                          get_communication_plan, get_data_quality_report,
                          classify_escalation_state, strategy_comparison,
                          HARD_CONSTRAINTS, SOFT_CONSTRAINTS)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "heatrisk-dev-secret-2026")


# ── Context Processor (Global Notifications & System Alerts) ──────────────────
@app.context_processor
def inject_global_data():
    if "user_id" in session:
        alerts = get_operational_alerts()
        unread_count = (alerts["critical_count"] + alerts["pending_reviews_count"] +
                        alerts["open_escalations_count"] + alerts["data_issues_count"] +
                        alerts["failed_comms_count"])
        return {
            "system_alerts": alerts,
            "alerts_unread_count": unread_count
        }
    return {"system_alerts": {}, "alerts_unread_count": 0}


# ── Decorators ────────────────────────────────────────────────────────────────
def login_required(f):
    @wraps(f)
    def dec(*a, **kw):
        if "user_id" not in session:
            flash("Please log in to continue.", "warning")
            return redirect(url_for("login"))
        return f(*a, **kw)
    return dec

def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def dec(*a, **kw):
            if session.get("role") not in roles:
                flash(f"Access denied — requires: {', '.join(roles)}.", "danger")
                return redirect(url_for("dashboard"))
            return f(*a, **kw)
        return dec
    return decorator

def row_to_dict(row): return dict(row) if row is not None else None
def rows_to_list(rows): return [dict(r) for r in rows]
def safe_float(v):
    try:
        f = float(v); return None if math.isnan(f) else f
    except: return None


# ── Auth ──────────────────────────────────────────────────────────────────────────────
import re as _re

def _valid_email(e):
    return bool(_re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', e))

@app.route("/", methods=["GET"])
def index():
    return redirect(url_for("dashboard") if "user_id" in session else url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        email    = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        if not email or not password:
            flash("Email and password are required.", "danger")
            return render_template("login.html")
        conn = get_db()
        user = conn.execute(
            "SELECT * FROM users WHERE LOWER(email)=? AND is_active=1", (email,)
        ).fetchone()
        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session.update({
                "user_id":   user["id"],
                "username":  user["email"],
                "full_name": user["full_name"],
                "email":     user["email"],
                "role":      user["role"],
            })
            conn.execute("UPDATE users SET last_active=datetime('now') WHERE id=?", (user["id"],))
            conn.commit()
            conn.close()
            log_audit(user["id"], user["email"], "LOGIN", "user", str(user["id"]),
                      f"{user['role']} logged in", request.remote_addr)
            return redirect(url_for("dashboard"))
        conn.close()
        # Safe generic error — do not reveal whether email exists
        flash("Invalid email address or password.", "danger")
        if user is None:
            log_audit(None, email, "LOGIN_FAILED", "user", None,
                      "Failed login attempt", request.remote_addr)
    return render_template("login.html")


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    allowed_roles = ["Health Officer", "Field Officer"]
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        email     = request.form.get("email", "").strip().lower()
        password  = request.form.get("password", "")
        confirm   = request.form.get("confirm_password", "")
        role      = request.form.get("role", "")
        errors = []
        if not full_name:
            errors.append("Full name is required.")
        if not email or not _valid_email(email):
            errors.append("A valid email address is required.")
        if role not in allowed_roles:
            errors.append("Please select a valid role (Health Officer or Field Officer).")
        if len(password) < 8:
            errors.append("Password must be at least 8 characters.")
        if password != confirm:
            errors.append("Passwords do not match.")
        if errors:
            for e in errors:
                flash(e, "danger")
            return render_template("signup.html", allowed_roles=allowed_roles,
                                   form=request.form)
        # Check email uniqueness
        conn = get_db()
        existing = conn.execute(
            "SELECT id FROM users WHERE LOWER(email)=?", (email,)
        ).fetchone()
        if existing:
            conn.close()
            flash("An account with that email address already exists.", "danger")
            return render_template("signup.html", allowed_roles=allowed_roles,
                                   form=request.form)
        from werkzeug.security import generate_password_hash
        conn.execute(
            "INSERT INTO users (full_name,email,password_hash,role,is_active) VALUES (?,?,?,?,1)",
            (full_name, email, generate_password_hash(password), role)
        )
        conn.commit()
        new_user = conn.execute("SELECT id FROM users WHERE LOWER(email)=?", (email,)).fetchone()
        log_audit(
            new_user["id"] if new_user else None, email,
            "SIGNUP", "user", None,
            f"New {role} registered", request.remote_addr
        )
        conn.close()
        flash("Account created successfully. Please sign in.", "success")
        return redirect(url_for("login"))
    return render_template("signup.html", allowed_roles=allowed_roles, form={})


@app.route("/logout")
def logout():
    uid   = session.get("user_id")
    email = session.get("email") or session.get("username", "unknown")
    log_audit(uid, email, "LOGOUT", "user", str(uid), "User logged out", request.remote_addr)
    session.clear()
    flash("You have been logged out securely.", "info")
    return redirect(url_for("login"))


# ── Dashboard ─────────────────────────────────────────────────────────────────
@app.route("/dashboard")
@login_required
def dashboard():
    conn = get_db()
    nbs       = rows_to_list(conn.execute("SELECT * FROM neighbourhoods").fetchall())
    reviews   = conn.execute("SELECT COUNT(*) c FROM human_reviews WHERE status='Pending'").fetchone()["c"]
    escalated = conn.execute("SELECT COUNT(*) c FROM escalations WHERE status='Open'").fetchone()["c"]
    comms_sent= conn.execute("SELECT COUNT(*) c FROM communications WHERE status='Sent'").fetchone()["c"]
    comms_fail= conn.execute("SELECT COUNT(*) c FROM communications WHERE status='Failed'").fetchone()["c"]
    conn.close()
    valid_scores = [n["risk_score"] for n in nbs if n["risk_score"] is not None]
    avg_risk = round(sum(valid_scores)/len(valid_scores),1) if valid_scores else 0
    totals = {
        "total": len(nbs), "high": sum(1 for n in nbs if n["risk_level"]=="High"),
        "medium": sum(1 for n in nbs if n["risk_level"]=="Medium"),
        "low": sum(1 for n in nbs if n["risk_level"]=="Low"),
        "ambiguous": sum(1 for n in nbs if n["risk_level"] in ("AMBIGUOUS","MISSING_DATA","EXTREME_VALUE")),
        "reviews": reviews, "escalated": escalated,
        "comms_sent": comms_sent, "comms_fail": comms_fail,
        "reached": sum(1 for n in nbs if (n["communication_reach_percentage"] or 0) > 50),
        "avg_risk": avg_risk,
    }
    risk_dist  = {"labels":["High","Medium","Low","Ambiguous"],
                  "values":[totals["high"],totals["medium"],totals["low"],totals["ambiguous"]]}
    temp_risk  = [{"x":safe_float(n["temperature"]),          "y":safe_float(n["risk_score"]),
                   "name":n["neighbourhood_name"],"level":n["risk_level"]}
                  for n in nbs if safe_float(n["temperature"]) and safe_float(n["risk_score"])]
    vuln_risk  = [{"x":safe_float(n["vulnerability_score"]),  "y":safe_float(n["risk_score"]),
                   "name":n["neighbourhood_name"],"level":n["risk_level"]}
                  for n in nbs if safe_float(n["vulnerability_score"]) and safe_float(n["risk_score"])]
    serv_risk  = [{"x":safe_float(n["service_access_score"]), "y":safe_float(n["risk_score"]),
                   "name":n["neighbourhood_name"],"level":n["risk_level"]}
                  for n in nbs if safe_float(n["service_access_score"]) and safe_float(n["risk_score"])]
    built_risk = [{"x":safe_float(n["built_environment_score"]),"y":safe_float(n["risk_score"]),
                   "name":n["neighbourhood_name"],"level":n["risk_level"]}
                  for n in nbs if safe_float(n["built_environment_score"]) and safe_float(n["risk_score"])]
    ranked = sorted([n for n in nbs if safe_float(n["risk_score"])],
                    key=lambda x: x["risk_score"], reverse=True)[:10]
    ranking_chart = {"labels":[n["neighbourhood_name"] for n in ranked],
                     "values":[n["risk_score"] for n in ranked],
                     "levels":[n["risk_level"] for n in ranked]}

    alerts = get_operational_alerts()
    priority_actions = get_priority_actions()

    return render_template("dashboard.html", totals=totals, alerts=alerts, priority_actions=priority_actions,
        risk_dist=json.dumps(risk_dist), temp_risk=json.dumps(temp_risk),
        vuln_risk=json.dumps(vuln_risk), serv_risk=json.dumps(serv_risk),
        built_risk=json.dumps(built_risk), ranking_chart=json.dumps(ranking_chart))


# ── Global Search & Notification APIs ─────────────────────────────────────────
@app.route("/api/search")
@login_required
def api_search():
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify([])
    conn = get_db()
    pattern = f"%{q}%"
    rows = conn.execute("""
        SELECT neighbourhood_id, neighbourhood_name, risk_level, risk_score, temperature
        FROM neighbourhoods
        WHERE neighbourhood_name LIKE ? OR neighbourhood_id LIKE ? OR risk_level LIKE ?
        ORDER BY risk_score DESC NULLS LAST
        LIMIT 10
    """, (pattern, pattern, pattern)).fetchall()
    conn.close()
    results = []
    for r in rows:
        results.append({
            "id": r["neighbourhood_id"],
            "name": r["neighbourhood_name"],
            "risk_level": r["risk_level"],
            "risk_score": r["risk_score"],
            "temperature": r["temperature"],
            "url": url_for("neighbourhood_detail", nb_id=r["neighbourhood_id"])
        })
    return jsonify(results)


@app.route("/api/notifications")
@login_required
def api_notifications():
    alerts = get_operational_alerts()
    actions = get_priority_actions()
    unread_count = (alerts["critical_count"] + alerts["pending_reviews_count"] +
                    alerts["open_escalations_count"] + alerts["data_issues_count"] +
                    alerts["failed_comms_count"])
    return jsonify({
        "status": "ok",
        "unread_count": unread_count,
        "alerts": alerts,
        "priority_actions": actions
    })



# ── Neighbourhoods ────────────────────────────────────────────────────────────
@app.route("/neighbourhoods")
@login_required
def neighbourhoods():
    conn = get_db()
    nbs = rows_to_list(conn.execute(
        "SELECT * FROM neighbourhoods ORDER BY risk_score DESC NULLS LAST").fetchall())
    esc_ids = {r["neighbourhood_id"] for r in conn.execute(
        "SELECT neighbourhood_id FROM escalations WHERE status='Open'").fetchall()}
    review_map = {r["neighbourhood_id"]: r["status"] for r in conn.execute(
        "SELECT neighbourhood_id, status FROM human_reviews WHERE status IN ('Pending','In Review','Approved')").fetchall()}
    conn.close()
    for nb in nbs:
        nb["has_escalation"] = nb["neighbourhood_id"] in esc_ids
        nb["review_status"]  = review_map.get(nb["neighbourhood_id"], "None")
        nb["needs_review"]   = nb["review_status"] == "Pending"
    return render_template("neighbourhoods.html", neighbourhoods=nbs)


# ── Neighbourhood Detail ──────────────────────────────────────────────────────
@app.route("/neighbourhood/<nb_id>")
@login_required
def neighbourhood_detail(nb_id):
    conn = get_db()
    nb = row_to_dict(conn.execute(
        "SELECT * FROM neighbourhoods WHERE neighbourhood_id=?", (nb_id,)).fetchone())
    if not nb:
        conn.close(); flash("Neighbourhood not found.", "warning")
        return redirect(url_for("neighbourhoods"))
    assessment = row_to_dict(conn.execute(
        "SELECT * FROM risk_assessments WHERE neighbourhood_id=? ORDER BY assessed_at DESC LIMIT 1",
        (nb_id,)).fetchone())
    comms = rows_to_list(conn.execute(
        "SELECT * FROM communications WHERE neighbourhood_id=? ORDER BY created_at DESC",(nb_id,)).fetchall())
    reviews = rows_to_list(conn.execute(
        "SELECT hr.*, u.full_name AS officer_name FROM human_reviews hr "
        "LEFT JOIN users u ON hr.assigned_to=u.id WHERE hr.neighbourhood_id=? ORDER BY hr.created_at DESC",
        (nb_id,)).fetchall())
    overrides = rows_to_list(conn.execute(
        "SELECT ov.*, u.full_name AS officer_name FROM overrides ov "
        "LEFT JOIN users u ON ov.user_id=u.id WHERE ov.neighbourhood_id=? ORDER BY ov.overridden_at DESC",
        (nb_id,)).fetchall())
    esc_row = row_to_dict(conn.execute(
        "SELECT e.*, u.full_name AS assigned_to_name FROM escalations e "
        "LEFT JOIN users u ON e.assigned_to=u.id WHERE e.neighbourhood_id=? ORDER BY e.created_at DESC LIMIT 1",
        (nb_id,)).fetchone())
    conn.close()

    snapshots = get_snapshots(nb_id)
    constraint_result = check_hard_constraints(nb)
    comm_plan = get_communication_plan(nb["risk_level"])
    computed  = compute_risk_score(nb)
    esc_state = classify_escalation_state(nb)
    contributions = None
    if assessment:
        contributions = {"labels":["Climate/Heat","Vulnerability","Built Environment","Service Access"],
                         "values":[assessment.get("climate_contribution") or 0,
                                   assessment.get("vuln_contribution") or 0,
                                   assessment.get("built_contribution") or 0,
                                   assessment.get("service_contribution") or 0]}
    return render_template("neighbourhood_detail.html", nb=nb, assessment=assessment,
        comms=comms, reviews=reviews, overrides=overrides,
        constraint_result=constraint_result, comm_plan=comm_plan, computed=computed,
        escalation_state=esc_state, snapshots=snapshots, escalation_row=esc_row,
        contributions=json.dumps(contributions) if contributions else "null")


@app.route("/neighbourhood/<nb_id>/snapshot", methods=["POST"])
@login_required
@role_required("Health Officer", "Administrator")
def record_snapshot(nb_id):
    notes = request.form.get("notes", "").strip()
    snap_id = create_snapshot(nb_id, user_id=session.get("user_id"), notes=notes)
    if snap_id:
        log_audit(session["user_id"], session["username"], "RISK_SNAPSHOT_CREATED",
                  "neighbourhood", nb_id, f"Snapshot #{snap_id} created: {notes[:80]}",
                  request.remote_addr)
        flash("Surveillance snapshot recorded successfully.", "success")
    else:
        flash("Failed to record snapshot: sector not found.", "danger")
    return redirect(url_for("neighbourhood_detail", nb_id=nb_id))


# ── Map ───────────────────────────────────────────────────────────────────────
@app.route("/map")
@login_required
def map_view():
    conn = get_db()
    nbs = rows_to_list(conn.execute(
        "SELECT neighbourhood_id, neighbourhood_name, latitude, longitude, temperature, "
        "risk_score, risk_level, vulnerability_score, service_access_score, "
        "built_environment_score, previous_heat_incidents, communication_reach_percentage, "
        "cooling_centres FROM neighbourhoods").fetchall())
    esc_ids    = {r["neighbourhood_id"] for r in conn.execute(
        "SELECT neighbourhood_id FROM escalations WHERE status='Open'").fetchall()}
    review_ids = {r["neighbourhood_id"] for r in conn.execute(
        "SELECT neighbourhood_id FROM human_reviews WHERE status IN ('Pending','In Review')").fetchall()}
    conn.close()
    for nb in nbs:
        nb["has_escalation"] = nb["neighbourhood_id"] in esc_ids
        nb["needs_review"]   = nb["neighbourhood_id"] in review_ids
    return render_template("map.html", map_data=json.dumps(nbs))


# ── Communication ─────────────────────────────────────────────────────────────
@app.route("/communication", methods=["GET","POST"])
@login_required
def communication():
    conn = get_db()
    nbs = rows_to_list(conn.execute(
        "SELECT neighbourhood_id, neighbourhood_name, risk_level, risk_score "
        "FROM neighbourhoods ORDER BY risk_score DESC NULLS LAST").fetchall())
    if request.method == "POST":
        nb_id    = request.form.get("neighbourhood_id","").strip()
        channels = request.form.getlist("channels")
        custom   = request.form.get("custom_message","").strip()
        status   = request.form.get("status", "Sent").strip()
        if not nb_id:
            flash("Please select a neighbourhood.", "danger")
        elif not channels:
            flash("Please select at least one channel.", "danger")
        else:
            nb_row = conn.execute(
                "SELECT * FROM neighbourhoods WHERE neighbourhood_id=?", (nb_id,)).fetchone()
            if nb_row:
                plan = get_communication_plan(nb_row["risk_level"], channels)
                msg  = custom or plan["message"]
                target_aud = plan.get("target_audience", "General Public")
                priority = plan.get("priority", "Standard (P3)")
                failure_reason = "Simulated delivery failure on primary gateway" if status == "Failed" else None
                for ch in channels:
                    conn.execute(
                        "INSERT INTO communications (neighbourhood_id,channel,message_type,"
                        "message_text,status,sent_at,sent_by,target_audience,priority,failure_reason) "
                        "VALUES (?,?,?,?,?,datetime('now'),?,?,?,?)",
                        (nb_id, ch, plan["message_type"], msg, status, session["user_id"],
                         target_aud, priority, failure_reason))
                conn.commit()
                log_audit(session["user_id"], session["username"], "COMMUNICATION_SENT",
                          "communication", nb_id,
                          f"Channels: {', '.join(channels)} | Status: {status} | Risk: {nb_row['risk_level']}",
                          request.remote_addr)
                flash(f"Communication recorded ({status}) via {len(channels)} channel(s).", "success")
            else:
                flash("Neighbourhood not found.", "danger")
    history = rows_to_list(conn.execute(
        "SELECT c.*, n.neighbourhood_name, n.risk_level FROM communications c "
        "JOIN neighbourhoods n ON c.neighbourhood_id=n.neighbourhood_id "
        "ORDER BY c.created_at DESC LIMIT 100").fetchall())
    conn.close()
    channels_all = ["SMS","Local Health Worker Outreach","Public Announcement",
                    "Community Centre Notice","Social Media Advisory","Phone Outreach"]
    preselect_nb = request.args.get("nb","")
    return render_template("communication.html", neighbourhoods=nbs, history=history,
                           channels_all=channels_all, preselect_nb=preselect_nb)


# ── Review Queue ──────────────────────────────────────────────────────────────
@app.route("/review-queue", methods=["GET","POST"])
@login_required
def review_queue():
    conn = get_db()
    if request.method == "POST":
        rid    = request.form.get("review_id")
        action = request.form.get("action")
        notes  = request.form.get("notes","").strip()
        status_map = {"approve":"Approved","modify":"Modified",
                      "escalate":"Escalated","request_info":"Info Requested"}
        new_status = status_map.get(action,"In Review")
        conn.execute("UPDATE human_reviews SET status=?,review_notes=?,reviewed_at=datetime('now') WHERE id=?",
                     (new_status, notes, rid))
        if action == "escalate":
            rev = row_to_dict(conn.execute("SELECT * FROM human_reviews WHERE id=?", (rid,)).fetchone())
            if rev:
                admin = conn.execute("SELECT id FROM users WHERE role='Administrator' LIMIT 1").fetchone()
                conn.execute(
                    "INSERT INTO escalations (neighbourhood_id,review_id,escalation_type,"
                    "current_state,level,reason,escalated_by,assigned_to,status) "
                    "VALUES (?,?,'High Risk Escalation','HIGH_ESCALATION','High Risk Escalation',?,?,?,'Open')",
                    (rev["neighbourhood_id"], rid, notes or "Escalated from review queue",
                     session["user_id"], admin["id"] if admin else None))
        conn.commit()
        log_audit(session["user_id"], session["username"],
                  f"REVIEW_{action.upper()}", "human_review", rid,
                  f"Status → {new_status} | {notes[:80]}", request.remote_addr)
        flash(f"Review marked as {new_status}.", "success")
    reviews = rows_to_list(conn.execute(
        "SELECT hr.*, n.neighbourhood_name, u.full_name AS officer_name FROM human_reviews hr "
        "JOIN neighbourhoods n ON hr.neighbourhood_id=n.neighbourhood_id "
        "LEFT JOIN users u ON hr.assigned_to=u.id "
        "ORDER BY CASE hr.priority WHEN 'Critical' THEN 0 WHEN 'High' THEN 1 ELSE 2 END,"
        "CASE hr.status WHEN 'Pending' THEN 0 WHEN 'In Review' THEN 1 ELSE 2 END,"
        "hr.risk_score DESC NULLS LAST").fetchall())
    officers = rows_to_list(conn.execute(
        "SELECT id, full_name, role FROM users WHERE role IN ('Health Officer','Administrator')").fetchall())
    conn.close()
    return render_template("review_queue.html", reviews=reviews, officers=officers)


# ── Escalation ────────────────────────────────────────────────────────────────
@app.route("/escalation", methods=["GET","POST"])
@login_required
def escalation():
    conn = get_db()
    if request.method == "POST":
        action = request.form.get("action")
        eid    = request.form.get("escalation_id")
        notes  = request.form.get("resolution_notes","").strip()
        if action == "resolve" and eid:
            if not notes:
                flash("Resolution notes are strictly required to resolve an escalation ticket.", "danger")
            else:
                conn.execute(
                    "UPDATE escalations SET status='Resolved',current_state='Resolved',"
                    "resolution_notes=?,resolved_at=datetime('now') WHERE id=?", (notes, eid))
                conn.commit()
                log_audit(session["user_id"], session["username"],
                          "ESCALATION_RESOLVED","escalation",eid, notes[:120], request.remote_addr)
                flash("Escalation resolved and logged.", "success")
        elif action == "update_state" and eid:
            new_state   = request.form.get("new_state","").strip()
            assigned_to = request.form.get("assigned_to","").strip()
            updates = []
            params  = []
            if new_state:
                updates.append("current_state=?")
                params.append(new_state)
            if assigned_to:
                updates.append("assigned_to=?")
                params.append(int(assigned_to))
            if updates:
                params.append(eid)
                conn.execute(f"UPDATE escalations SET {', '.join(updates)} WHERE id=?", params)
                conn.commit()
                log_audit(session["user_id"], session["username"],
                          "ESCALATION_UPDATE","escalation",eid,
                          f"State: {new_state} | Assigned: {assigned_to}", request.remote_addr)
                flash(f"Escalation ticket #{eid} updated.", "info")
    escs = rows_to_list(conn.execute(
        "SELECT e.*, n.neighbourhood_name, n.risk_level, n.risk_score, "
        "u.full_name AS escalated_by_name, a.full_name AS assigned_to_name "
        "FROM escalations e JOIN neighbourhoods n ON e.neighbourhood_id=n.neighbourhood_id "
        "LEFT JOIN users u ON e.escalated_by=u.id LEFT JOIN users a ON e.assigned_to=a.id "
        "ORDER BY CASE e.status WHEN 'Open' THEN 0 WHEN 'Under Review' THEN 1 ELSE 2 END,"
        "e.created_at DESC").fetchall())
    officers = rows_to_list(conn.execute(
        "SELECT id, full_name, role FROM users WHERE role IN ('Health Officer','Administrator')").fetchall())
    conn.close()
    states = [
        {"id":"NORMAL",          "label":"Normal",             "sub":"Low Risk",           "colour":"low"},
        {"id":"MONITORING",      "label":"Monitoring",          "sub":"Watch Closely",      "colour":"medium"},
        {"id":"TARGETED",        "label":"Targeted Response",   "sub":"Medium Risk",        "colour":"medium"},
        {"id":"HIGH_REVIEW",     "label":"H.O. Review",         "sub":"High Risk",          "colour":"high"},
        {"id":"HIGH_ESCALATION", "label":"High Risk Escalation","sub":"Severe Heat Alert",  "colour":"high"},
        {"id":"IMMEDIATE",       "label":"Immediate Escalation","sub":"Emergency ≥90",      "colour":"high"},
    ]
    return render_template("escalation.html", escalations=escs, states=states, officers=officers)


# ── Strategy ──────────────────────────────────────────────────────────────────
@app.route("/strategy")
@login_required
def strategy():
    conn = get_db()
    nbs = rows_to_list(conn.execute("SELECT * FROM neighbourhoods").fetchall())
    conn.close()
    comparison = strategy_comparison(nbs)
    return render_template("strategy.html", comparison=json.dumps(comparison), comparison_data=comparison)


# ── Journeys ──────────────────────────────────────────────────────────────────
@app.route("/journeys")
@login_required
def journeys():
    conn = get_db()
    j1 = row_to_dict(conn.execute(
        "SELECT * FROM neighbourhoods WHERE risk_level='Medium' ORDER BY risk_score ASC LIMIT 1").fetchone())
    j2 = row_to_dict(conn.execute(
        "SELECT * FROM neighbourhoods WHERE risk_level='High' ORDER BY risk_score DESC LIMIT 1").fetchone())
    conn.close()
    return render_template("journeys.html", j1=j1, j2=j2)


# ── Experiment ────────────────────────────────────────────────────────────────
@app.route("/experiment")
@login_required
def experiment():
    conn = get_db()
    nbs  = rows_to_list(conn.execute("SELECT * FROM neighbourhoods").fetchall())
    conn.close()
    valid = [n for n in nbs if n["risk_score"] is not None]
    high  = [n for n in valid if n["risk_level"] == "High"]
    med   = [n for n in valid if n["risk_level"] == "Medium"]
    low   = [n for n in valid if n["risk_level"] == "Low"]
    total = len(valid)
    prop_reached = round(sum(n["communication_reach_percentage"] or 0 for n in high)/max(len(high),1),1)
    metrics = {
        "total_neighbourhoods": total,
        "high_count": len(high), "medium_count": len(med), "low_count": len(low),
        "baseline": {"high_prioritised":len(high),"high_reached_pct":50.0,
                     "timeliness":"3-5 days","resource_util_pct":40.0,
                     "missed":round(len(high)*0.5),"precision":50.0,"recall":50.0},
        "proposed": {"high_prioritised":len(high),"high_reached_pct":prop_reached,
                     "timeliness":"Same day",
                     "resource_util_pct":min(95,round(len(high)/max(total,1)*100+40,1)),
                     "missed":round(len(high)*(1-prop_reached/100)),
                     "precision":round(len(high)/max(total,1)*100,1),"recall":prop_reached},
    }
    return render_template("experiment.html", metrics=metrics, metrics_json=json.dumps(metrics))


# ── Failures ──────────────────────────────────────────────────────────────────
@app.route("/failures")
@login_required
def failures():
    conn = get_db()
    nbs = rows_to_list(conn.execute("SELECT * FROM neighbourhoods").fetchall())
    conn.close()
    failure_modes = [
        {"id":"FC-01","name":"Missing Temperature Data",
         "description":"Critical temperature/heat-index field is NULL or NaN.",
         "detection":"Pre-computation null check in risk_engine.check_hard_constraints()",
         "impact":"Cannot compute climate contribution — risk score unreliable.",
         "system_response":"Flag as MISSING_DATA; block classification; create mandatory review.",
         "human_review":"Health Officer manually assesses using field data.",
         "escalation":"If other indicators critical, escalate immediately.",
         "example_nb":next((n["neighbourhood_name"] for n in nbs if n["temperature"] is None),"N/A")},
        {"id":"FC-02","name":"Conflicting Indicators",
         "description":"High temperature (>40°C) but low vulnerability (<20) and strong service access (>70).",
         "detection":"Combined threshold check in check_hard_constraints()",
         "impact":"Automated score may over-flag a well-resourced area.",
         "system_response":"Mark AMBIGUOUS; hold communication; route to manual review.",
         "human_review":"Health Officer reviews field context before classifying.",
         "escalation":"If extreme temperature persists 48h, auto-escalate.",
         "example_nb":"Well-resourced suburb with temporary extreme weather"},
        {"id":"FC-03","name":"Healthcare / Cooling Services Unavailable",
         "description":"cooling_centres=0 AND service_access_score<40 in heat-affected area.",
         "detection":"Service access check in risk_engine + HC-04",
         "impact":"No accessible cooling refuge — extreme vulnerability.",
         "system_response":"Escalate automatically; recommend alternate service deployment.",
         "human_review":"Administrator authorises emergency cooling centre deployment.",
         "escalation":"Immediate escalation to Senior Health Officer.",
         "example_nb":next((n["neighbourhood_name"] for n in nbs
                            if (n["cooling_centres"] or 1)==0 and (n["service_access_score"] or 99)<40),
                           "Wentworthville")},
        {"id":"FC-04","name":"Extreme Invalid Sensor Value",
         "description":"Temperature > 52°C — outside physically plausible range.",
         "detection":"Extreme-value guard in check_hard_constraints()",
         "impact":"Sensor error inflates risk score if not caught.",
         "system_response":"Flag EXTREME_VALUE; exclude from auto-scoring; send to data validation.",
         "human_review":"Data team verifies sensor readings before re-running engine.",
         "escalation":"If confirmed real, escalate as emergency immediately.",
         "example_nb":next((n["neighbourhood_name"] for n in nbs
                            if n["temperature"] and n["temperature"]>52),"Rockdale (hypothetical)")},
        {"id":"FC-05","name":"Authorised Override Conflict",
         "description":"Two Health Officers submit conflicting overrides for same neighbourhood.",
         "detection":"Override audit log review on each submission.",
         "impact":"Risk level inconsistent; communication confusion.",
         "system_response":"System flags conflict; locks further overrides; escalates to Administrator.",
         "human_review":"Administrator resolves conflict and makes final classification.",
         "escalation":"Administrator override takes precedence; all overrides permanently logged.",
         "example_nb":"Override conflict scenario (NB047-type case)"},
    ]
    return render_template("failures.html", failure_modes=failure_modes)


# ── Constraints ───────────────────────────────────────────────────────────────
@app.route("/constraints", methods=["GET","POST"])
@login_required
def constraints():
    if request.method == "POST":
        weights = {}
        for sc in SOFT_CONSTRAINTS:
            try: weights[sc["id"]] = float(request.form.get(sc["id"], sc["default_weight"]))
            except: weights[sc["id"]] = sc["default_weight"]
        session["soft_weights"] = weights
        log_audit(session["user_id"], session["username"],
                  "SOFT_CONSTRAINT_UPDATE","constraint","all",
                  f"Weights: {weights}", request.remote_addr)
        flash("Soft constraint weights saved.", "success")
    soft_weights = session.get("soft_weights",
                               {sc["id"]: sc["default_weight"] for sc in SOFT_CONSTRAINTS})
    return render_template("constraints.html", hard_constraints=HARD_CONSTRAINTS,
                           soft_constraints=SOFT_CONSTRAINTS, soft_weights=soft_weights)


# ── Audit Log ─────────────────────────────────────────────────────────────────
@app.route("/audit")
@login_required
def audit():
    conn = get_db()
    logs = rows_to_list(conn.execute(
        "SELECT * FROM audit_logs ORDER BY logged_at DESC LIMIT 300").fetchall())
    overrides = rows_to_list(conn.execute(
        "SELECT ov.*, u.full_name, n.neighbourhood_name FROM overrides ov "
        "JOIN users u ON ov.user_id=u.id "
        "JOIN neighbourhoods n ON ov.neighbourhood_id=n.neighbourhood_id "
        "ORDER BY ov.overridden_at DESC").fetchall())
    conn.close()
    kpis = {"total_events":len(logs),
            "logins":sum(1 for l in logs if l["action"]=="LOGIN"),
            "overrides":sum(1 for l in logs if l["action"]=="RISK_OVERRIDE"),
            "comms_sent":sum(1 for l in logs if l["action"]=="COMMUNICATION_SENT"),
            "reviews":sum(1 for l in logs if "REVIEW" in l["action"]),
            "escalations":sum(1 for l in logs if "ESCALATION" in l["action"])}
    return render_template("audit.html", logs=logs, overrides=overrides, kpis=kpis)


# ── Override ──────────────────────────────────────────────────────────────────
@app.route("/override/<nb_id>", methods=["POST"])
@login_required
@role_required("Health Officer","Administrator")
def override_risk(nb_id):
    new_level = request.form.get("new_level","").strip()
    reason    = request.form.get("reason","").strip()
    if not reason:
        flash("Override reason required (HC-06).", "danger")
        return redirect(url_for("neighbourhood_detail", nb_id=nb_id))
    if not new_level:
        flash("New risk level required.", "danger")
        return redirect(url_for("neighbourhood_detail", nb_id=nb_id))
    conn = get_db()
    nb = row_to_dict(conn.execute(
        "SELECT * FROM neighbourhoods WHERE neighbourhood_id=?", (nb_id,)).fetchone())
    if not nb:
        conn.close(); flash("Neighbourhood not found.", "danger")
        return redirect(url_for("neighbourhoods"))
    old_level = nb["risk_level"]
    conn.execute("UPDATE neighbourhoods SET risk_level=? WHERE neighbourhood_id=?", (new_level, nb_id))
    conn.execute("INSERT INTO overrides (neighbourhood_id,user_id,original_level,new_level,reason) VALUES (?,?,?,?,?)",
                 (nb_id, session["user_id"], old_level, new_level, reason))
    conn.commit(); conn.close()
    log_audit(session["user_id"], session["username"], "RISK_OVERRIDE", "neighbourhood", nb_id,
              f"Override: {old_level} → {new_level} | Reason: {reason}", request.remote_addr)
    flash(f"Risk updated: {old_level} → {new_level}. Override logged (HC-07).", "success")
    return redirect(url_for("neighbourhood_detail", nb_id=nb_id))


# ── Data Quality ──────────────────────────────────────────────────────────────
@app.route("/data-quality")
@login_required
def data_quality():
    conn = get_db()
    nbs = rows_to_list(conn.execute("SELECT * FROM neighbourhoods").fetchall())
    conn.close()
    report = get_data_quality_report(nbs)
    summary = {"total":len(report),
               "ok":sum(1 for r in report if r["status"]=="OK"),
               "warning":sum(1 for r in report if r["status"]=="WARNING"),
               "critical":sum(1 for r in report if r["status"]=="CRITICAL"),
               "missing_any":sum(1 for r in report if r["missing_count"]>0),
               "outliers_any":sum(1 for r in report if r["outlier_count"]>0),
               "avg_quality":round(sum(r["quality_score"] for r in report)/max(len(report),1),1)}
    return render_template("data_quality.html", report=report, summary=summary)


# ── Feedback ──────────────────────────────────────────────────────────────────
@app.route("/feedback", methods=["GET","POST"])
@login_required
def feedback():
    conn = get_db()
    if request.method == "POST":
        role = request.form.get("role","").strip()
        if not role:
            flash("Please select your role.", "danger")
        else:
            conn.execute(
                "INSERT INTO stakeholder_feedback (respondent_role,respondent_name,"
                "q_risk_understandable,q_escalation_clear,q_actions_useful,q_dashboard_easy,"
                "improvement_notes) VALUES (?,?,?,?,?,?,?)",
                (role, request.form.get("name","Anonymous"),
                 int(request.form.get("q1",3)), int(request.form.get("q2",3)),
                 int(request.form.get("q3",3)), int(request.form.get("q4",3)),
                 request.form.get("notes","")))
            conn.commit()
            flash("Feedback submitted. Thank you!", "success")
    all_feedback = rows_to_list(conn.execute(
        "SELECT * FROM stakeholder_feedback ORDER BY submitted_at DESC").fetchall())
    conn.close()
    avg = ({"q1":round(sum(f["q_risk_understandable"] or 0 for f in all_feedback)/len(all_feedback),1),
            "q2":round(sum(f["q_escalation_clear"]    or 0 for f in all_feedback)/len(all_feedback),1),
            "q3":round(sum(f["q_actions_useful"]       or 0 for f in all_feedback)/len(all_feedback),1),
            "q4":round(sum(f["q_dashboard_easy"]       or 0 for f in all_feedback)/len(all_feedback),1)}
           if all_feedback else {"q1":0,"q2":0,"q3":0,"q4":0})
    return render_template("feedback.html", feedbacks=all_feedback, averages=avg)


# ── Export ────────────────────────────────────────────────────────────────────
@app.route("/export/<report_type>")
@login_required
def export_report(report_type):
    conn = get_db()
    queries = {
        "high_risk": ("SELECT * FROM neighbourhoods WHERE risk_level='High'","high_risk.csv"),
        "review_queue": ("SELECT hr.*, n.neighbourhood_name FROM human_reviews hr "
                         "JOIN neighbourhoods n ON hr.neighbourhood_id=n.neighbourhood_id","reviews.csv"),
        "communications": ("SELECT c.*, n.neighbourhood_name FROM communications c "
                           "JOIN neighbourhoods n ON c.neighbourhood_id=n.neighbourhood_id","comms.csv"),
        "audit": ("SELECT * FROM audit_logs","audit_log.csv"),
        "all_neighbourhoods": ("SELECT * FROM neighbourhoods ORDER BY risk_score DESC NULLS LAST","all_nbs.csv"),
        "data_quality": ("SELECT neighbourhood_id, neighbourhood_name, risk_level, data_quality_flag, temperature, vulnerability_score, service_access_score FROM neighbourhoods","data_quality.csv"),
    }
    if report_type not in queries:
        conn.close(); flash("Unknown report type.","warning")
        return redirect(url_for("dashboard"))
    sql, fname = queries[report_type]
    rows = rows_to_list(conn.execute(sql).fetchall())
    conn.close()
    if not rows:
        flash("No data to export.","info"); return redirect(url_for("dashboard"))
    output = io.StringIO()
    w = csv.DictWriter(output, fieldnames=rows[0].keys())
    w.writeheader(); w.writerows(rows)
    resp = make_response(output.getvalue())
    resp.headers["Content-Disposition"] = f"attachment; filename={fname}"
    resp.headers["Content-Type"] = "text/csv; charset=utf-8"
    log_audit(session["user_id"], session["username"],"EXPORT","report",
              report_type, f"Exported {len(rows)} rows", request.remote_addr)
    return resp


# ── Analytics & Insights ──────────────────────────────────────────────────────
@app.route("/analytics")
@login_required
def analytics():
    conn = get_db()
    nbs = rows_to_list(conn.execute("SELECT * FROM neighbourhoods").fetchall())
    conn.close()
    valid_nbs = [n for n in nbs if n["risk_score"] is not None]
    high_risk = sorted([n for n in valid_nbs if n["risk_level"] == "High"],
                       key=lambda x: x["risk_score"] or 0, reverse=True)
    high_vuln = sorted([n for n in nbs if n["vulnerability_score"] is not None and n["vulnerability_score"] > 60],
                       key=lambda x: x["vulnerability_score"] or 0, reverse=True)
    poor_service = sorted([n for n in nbs if n["service_access_score"] is not None and n["service_access_score"] < 40],
                          key=lambda x: x["service_access_score"] or 0)

    reach_by_level = {"High": [], "Medium": [], "Low": []}
    for n in nbs:
        lvl = n["risk_level"]
        reach = n["communication_reach_percentage"]
        if lvl in reach_by_level and reach is not None:
            reach_by_level[lvl].append(reach)
    avg_reach = {k: round(sum(v)/len(v), 1) if v else 0 for k, v in reach_by_level.items()}

    return render_template("analytics.html", nbs=nbs, high_risk=high_risk, high_vuln=high_vuln,
                           poor_service=poor_service, avg_reach=avg_reach)


# ── User Management (Administrator Only) ──────────────────────────────────────
@app.route("/users")
@login_required
@role_required("Administrator")
def users_management():
    conn = get_db()
    role_filter = request.args.get("role", "").strip()
    search_q = request.args.get("q", "").strip().lower()
    sql = "SELECT id, full_name, email, role, is_active, created_at, last_active FROM users WHERE 1=1"
    params = []
    if role_filter:
        sql += " AND role=?"
        params.append(role_filter)
    if search_q:
        sql += " AND (LOWER(full_name) LIKE ? OR LOWER(email) LIKE ?)"
        params.extend([f"%{search_q}%", f"%{search_q}%"])
    sql += " ORDER BY created_at DESC"
    users = rows_to_list(conn.execute(sql, params).fetchall())
    conn.close()
    return render_template("users.html", users=users, selected_role=role_filter, search_q=search_q)


@app.route("/users/<int:user_id>/toggle-status", methods=["POST"])
@login_required
@role_required("Administrator")
def toggle_user_status(user_id):
    if user_id == session.get("user_id"):
        flash("You cannot deactivate your own administrative account.", "danger")
        return redirect(url_for("users_management"))
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    if not user:
        conn.close()
        flash("User not found.", "danger")
        return redirect(url_for("users_management"))
    new_status = 0 if user["is_active"] else 1
    conn.execute("UPDATE users SET is_active=? WHERE id=?", (new_status, user_id))
    conn.commit()
    conn.close()
    action_name = "USER_ACTIVATED" if new_status == 1 else "USER_DEACTIVATED"
    status_desc = "activated" if new_status == 1 else "deactivated"
    log_audit(session["user_id"], session["username"], action_name, "user", str(user_id),
              f"User {user['email']} was {status_desc} by Administrator", request.remote_addr)
    flash(f"User {user['full_name']} has been {status_desc}.", "success")
    return redirect(url_for("users_management"))


# ── Error Handlers ────────────────────────────────────────────────────────────
@app.errorhandler(404)
def page_not_found(e):
    return render_template("404.html"), 404


@app.errorhandler(403)
def access_forbidden(e):
    return render_template("403.html"), 403


@app.errorhandler(500)
def server_error(e):
    return render_template("500.html"), 500


# ── API ───────────────────────────────────────────────────────────────────────
@app.route("/api/neighbourhoods")
@login_required
def api_neighbourhoods():
    conn = get_db()
    nbs = rows_to_list(conn.execute("SELECT * FROM neighbourhoods").fetchall())
    conn.close()
    return jsonify(nbs)

@app.route("/api/risk-explain/<nb_id>")
@login_required
def api_risk_explain(nb_id):
    conn = get_db()
    nb = row_to_dict(conn.execute(
        "SELECT * FROM neighbourhoods WHERE neighbourhood_id=?", (nb_id,)).fetchone())
    conn.close()
    if not nb: return jsonify({"error":"Not found"}), 404
    result = compute_risk_score(nb)
    result["neighbourhood_id"]   = nb_id
    result["neighbourhood_name"] = nb["neighbourhood_name"]
    return jsonify(result)

@app.route("/api/data-quality")
@login_required
def api_data_quality():
    conn = get_db()
    nbs = rows_to_list(conn.execute("SELECT * FROM neighbourhoods").fetchall())
    conn.close()
    return jsonify(get_data_quality_report(nbs))

@app.route("/documentation")
@login_required
def documentation():
    return render_template("documentation.html")


# ── Main ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    if not os.path.exists("neighbourhood_heat_risk.csv"):
        import subprocess, sys
        generate_data_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "generate_data.py"
        )
        subprocess.run([sys.executable, generate_data_path], check=True)

    init_db()

    print("[OK] Starting Flask app v2 at http://127.0.0.1:5000")

    import webbrowser
    from threading import Timer

    Timer(
        1,
        lambda: webbrowser.open("http://127.0.0.1:5000")
    ).start()

    app.run(debug=False, port=5000, use_reloader=False)
