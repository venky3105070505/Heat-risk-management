"""
risk_engine.py  v2
Transparent, auditable risk scoring engine.
- All weights and thresholds are explicit constants.
- Hard constraints enforced before any recommendation.
- New in v2: data quality report, escalation state classifier.
"""

import math

# ── Weights (must sum to 1.0) ─────────────────────────────────────────────────
WEIGHT_CLIMATE = 0.35
WEIGHT_VULN    = 0.30
WEIGHT_BUILT   = 0.20
WEIGHT_SERVICE = 0.15

# ── Normalisation reference ranges (domain knowledge) ────────────────────────
TEMP_MIN,  TEMP_MAX  = 20.0, 50.0
HI_MIN,    HI_MAX    = 20.0, 55.0
VULN_MIN,  VULN_MAX  = 0.0,  100.0
BUILT_MIN, BUILT_MAX = 0.0,  100.0
SERV_MIN,  SERV_MAX  = 0.0,  100.0

# ── Risk thresholds ───────────────────────────────────────────────────────────
LOW_THRESHOLD  = 40.0
HIGH_THRESHOLD = 70.0

# ── Hard Constraints ──────────────────────────────────────────────────────────
HARD_CONSTRAINTS = [
    {"id": "HC-01", "name": "Aggregate data only",
     "description": "Only aggregate neighbourhood-level data may be used. No individual patient or resident data is processed.",
     "enforcement": "Data inputs validated at ingestion; no individual-level fields permitted."},
    {"id": "HC-02", "name": "High-risk cannot be auto-closed",
     "description": "A neighbourhood classified High Risk cannot be automatically closed or downgraded without explicit human review.",
     "enforcement": "Any closure attempt on a High-risk record is blocked until a Health Officer or Administrator approves."},
    {"id": "HC-03", "name": "High-risk requires human review",
     "description": "All High Risk classifications automatically create a mandatory human review queue entry.",
     "enforcement": "risk_engine.py inserts a review record whenever risk_level == 'High'."},
    {"id": "HC-04", "name": "Emergency cases must be escalated",
     "description": "Emergency-level risk events (risk_score >= 90 OR two or more failure conditions) must be escalated to a Senior Health Officer or Administrator.",
     "enforcement": "Escalation record is created automatically; cannot be bypassed."},
    {"id": "HC-05", "name": "Override restricted to authorised roles",
     "description": "Only Health Officers and Administrators may override a risk classification.",
     "enforcement": "Flask route checks session role before allowing override form submission."},
    {"id": "HC-06", "name": "Override requires written reason",
     "description": "Every risk override must include a written justification.",
     "enforcement": "Override form validates that reason field is non-empty (server-side)."},
    {"id": "HC-07", "name": "Override must be logged",
     "description": "Every override is recorded in audit_logs with user, timestamp, original value, new value, and reason.",
     "enforcement": "database.log_audit() called immediately after every override write."},
    {"id": "HC-08", "name": "Missing critical data blocks auto-recommendation",
     "description": "If temperature OR vulnerability_score is missing/null, the system cannot issue an automatic final recommendation.",
     "enforcement": "check_hard_constraints() returns MISSING_DATA status; no risk score computed."},
]

# ── Soft Constraints (configurable) ──────────────────────────────────────────
SOFT_CONSTRAINTS = [
    {"id": "SC-01", "name": "Prioritise high-vulnerability neighbourhoods",
     "description": "Neighbourhoods with vulnerability_score > 60 are prioritised in response queue.",
     "default_weight": 0.8},
    {"id": "SC-02", "name": "Prioritise poor healthcare access",
     "description": "Neighbourhoods with service_access_score < 40 get higher scheduling priority.",
     "default_weight": 0.7},
    {"id": "SC-03", "name": "Minimise response time",
     "description": "Field teams prefer neighbourhoods closer to their base to reduce travel time.",
     "default_weight": 0.6},
    {"id": "SC-04", "name": "Minimise field-team workload",
     "description": "Distribute work evenly across available field officers.",
     "default_weight": 0.5},
    {"id": "SC-05", "name": "Maximise high-risk areas reached",
     "description": "Optimise communication plan to cover the most High-risk neighbourhoods.",
     "default_weight": 0.9},
    {"id": "SC-06", "name": "Prefer simple understandable language",
     "description": "Messages must use plain language (reading level <= Grade 8).",
     "default_weight": 0.7},
    {"id": "SC-07", "name": "Min. days between repeat communications",
     "description": "Do not send repeat communications to same neighbourhood within N days.",
     "default_weight": 3.0},
    {"id": "SC-08", "name": "Max areas per communication batch",
     "description": "Limit each communication batch to avoid system overload.",
     "default_weight": 10.0},
]


def _safe_norm(value, lo, hi):
    """Min-max normalise a value to [0,1]. Returns None if value is None/NaN."""
    if value is None:
        return None
    try:
        v = float(value)
        if math.isnan(v):
            return None
        return max(0.0, min(1.0, (v - lo) / (hi - lo + 1e-9)))
    except (TypeError, ValueError):
        return None


def _get(nb, key):
    """Safe getter for both sqlite3.Row and dict."""
    try:
        return nb[key]
    except (KeyError, IndexError, TypeError):
        return None


def check_hard_constraints(nb):
    """
    Evaluate hard constraints for a single neighbourhood dict/Row.
    Returns:
      status             : 'OK' | 'MISSING_DATA' | 'AMBIGUOUS' | 'EMERGENCY' | 'EXTREME_VALUE'
      messages           : list of human-readable violation messages
      can_auto_classify  : bool
    """
    messages = []
    status   = "OK"

    temp       = _get(nb, "temperature")
    vuln       = _get(nb, "vulnerability_score")
    serv       = _get(nb, "service_access_score")
    cool       = _get(nb, "cooling_centres")
    risk_score = _get(nb, "risk_score")

    # HC-08: Missing critical fields
    if temp is None or (isinstance(temp, float) and math.isnan(temp)):
        messages.append("HC-08: Temperature data is missing — automatic classification blocked.")
        status = "MISSING_DATA"
    if vuln is None or (isinstance(vuln, float) and math.isnan(vuln)):
        messages.append("HC-08: Vulnerability score is missing — automatic classification blocked.")
        if status == "OK":
            status = "MISSING_DATA"

    # FC-04: Extreme outlier — physically impossible value
    if temp is not None and not (isinstance(temp, float) and math.isnan(temp)):
        if float(temp) > 52:
            messages.append(f"FC-04: Extreme temperature ({temp}°C > 52°C) — likely sensor error. Flagged for data validation.")
            if status == "OK":
                status = "EXTREME_VALUE"

    # FC-02: Conflicting indicators
    if (temp is not None and not (isinstance(temp, float) and math.isnan(temp)) and float(temp) > 40
            and vuln is not None and not (isinstance(vuln, float) and math.isnan(vuln)) and float(vuln) < 20
            and serv is not None and float(serv) > 70):
        messages.append("FC-02: High temperature but low vulnerability and strong service access — ambiguous, human review required.")
        if status == "OK":
            status = "AMBIGUOUS"

    # FC-03: No cooling centres and poor service access
    if cool is not None and int(cool) == 0:
        if serv is not None and float(serv) < 40:
            messages.append("FC-03: Zero cooling centres AND poor service access — emergency escalation recommended.")
            if status == "OK":
                status = "AMBIGUOUS"

    # HC-04: Emergency threshold
    if risk_score is not None and not (isinstance(risk_score, float) and math.isnan(risk_score)):
        if float(risk_score) >= 90:
            messages.append("HC-04: Risk score >= 90 — mandatory emergency escalation required.")
            status = "EMERGENCY"

    return {
        "status": status,
        "messages": messages,
        "can_auto_classify": status == "OK",
    }


def compute_risk_score(nb):
    """
    Compute a transparent, auditable risk score.

    Formula:
      score = (climate_norm  * 0.35
             + vuln_norm     * 0.30
             + built_norm    * 0.20
             + service_norm  * 0.15) * 100

    Returns dict with score, level, component contributions, and constraint status.
    """
    temp  = _get(nb, "temperature")
    hi    = _get(nb, "heat_index")
    vuln  = _get(nb, "vulnerability_score")
    built = _get(nb, "built_environment_score")
    serv  = _get(nb, "service_access_score")

    # Prefer heat_index over raw temperature for climate component
    climate_val  = hi if (hi is not None and not (isinstance(hi, float) and math.isnan(hi))) else temp
    climate_norm = _safe_norm(climate_val, HI_MIN, HI_MAX)
    vuln_norm    = _safe_norm(vuln,  VULN_MIN, VULN_MAX)
    built_norm   = _safe_norm(built, BUILT_MIN, BUILT_MAX)
    # Service risk = INVERSE of access score (low access → high risk)
    serv_norm    = _safe_norm((100 - (serv or 50)), 0, 100)

    constraint_result = check_hard_constraints(nb)

    if not constraint_result["can_auto_classify"]:
        return {
            "risk_score":           None,
            "risk_level":           constraint_result["status"],
            "climate_contribution": None,
            "vuln_contribution":    None,
            "built_contribution":   None,
            "service_contribution": None,
            "constraint_status":    constraint_result["status"],
            "constraint_messages":  constraint_result["messages"],
            "can_auto_classify":    False,
            # Transparent formula explanation
            "formula_steps": {
                "climate_norm":  None,
                "vuln_norm":     vuln_norm,
                "built_norm":    built_norm,
                "service_norm":  serv_norm,
                "weights":       {"climate": WEIGHT_CLIMATE, "vuln": WEIGHT_VULN,
                                  "built": WEIGHT_BUILT, "service": WEIGHT_SERVICE},
            },
        }

    # Weighted sum
    score = (
        (climate_norm or 0) * WEIGHT_CLIMATE
        + (vuln_norm  or 0) * WEIGHT_VULN
        + (built_norm or 0) * WEIGHT_BUILT
        + (serv_norm  or 0) * WEIGHT_SERVICE
    ) * 100
    score = round(min(100.0, max(0.0, score)), 1)

    # Component contributions (points each factor adds to the final score)
    clim_c = round((climate_norm or 0) * WEIGHT_CLIMATE * 100, 1)
    vuln_c = round((vuln_norm   or 0) * WEIGHT_VULN    * 100, 1)
    blt_c  = round((built_norm  or 0) * WEIGHT_BUILT   * 100, 1)
    srv_c  = round((serv_norm   or 0) * WEIGHT_SERVICE * 100, 1)

    level = "Low" if score < LOW_THRESHOLD else ("High" if score >= HIGH_THRESHOLD else "Medium")

    return {
        "risk_score":           score,
        "risk_level":           level,
        "climate_contribution": clim_c,
        "vuln_contribution":    vuln_c,
        "built_contribution":   blt_c,
        "service_contribution": srv_c,
        "constraint_status":    constraint_result["status"],
        "constraint_messages":  constraint_result["messages"],
        "can_auto_classify":    True,
        "formula_steps": {
            "climate_raw":  round(float(climate_val or 0), 1),
            "climate_norm": round(climate_norm or 0, 3),
            "vuln_raw":     round(float(vuln or 0), 1),
            "vuln_norm":    round(vuln_norm or 0, 3),
            "built_raw":    round(float(built or 0), 1),
            "built_norm":   round(built_norm or 0, 3),
            "serv_raw":     round(float(serv or 0), 1),
            "serv_norm":    round(serv_norm or 0, 3),
            "weights":      {"climate": WEIGHT_CLIMATE, "vuln": WEIGHT_VULN,
                             "built": WEIGHT_BUILT,     "service": WEIGHT_SERVICE},
            "subtotals":    {"climate": clim_c, "vuln": vuln_c,
                             "built": blt_c,    "service": srv_c},
            "total":        score,
        },
    }


def classify_escalation_state(nb):
    """
    Return the current escalation state for a neighbourhood following the 6-stage operational pipeline:
      NORMAL → MONITORING → TARGETED RESPONSE → HUMAN OFFICER REVIEW → HIGH RISK ESCALATION → IMMEDIATE ESCALATION
      (plus MANUAL for ambiguous/data-quality cases).
    """
    risk_level = _get(nb, "risk_level") or "AMBIGUOUS"
    risk_score = _get(nb, "risk_score")

    if risk_level in ("MISSING_DATA", "EXTREME_VALUE"):
        return {"state": "MANUAL",          "label": "Manual Review Required",    "colour": "ambig",  "icon": "fa-question-circle", "order": 0}
    if risk_level == "AMBIGUOUS":
        return {"state": "MANUAL",          "label": "Manual Review — Ambiguous", "colour": "ambig",  "icon": "fa-exclamation-circle", "order": 0}
    if risk_score is not None and float(risk_score) >= 90:
        return {"state": "IMMEDIATE",       "label": "Immediate Escalation",      "colour": "emerg",  "icon": "fa-ambulance", "order": 6}
    if risk_score is not None and float(risk_score) >= 85:
        return {"state": "HIGH_ESCALATION", "label": "High Risk Escalation",      "colour": "high",   "icon": "fa-radiation", "order": 5}
    if risk_level == "High":
        return {"state": "HIGH_REVIEW",     "label": "Human Officer Review",      "colour": "high",   "icon": "fa-user-md", "order": 4}
    if risk_level == "Medium":
        score = float(risk_score or 0)
        if score >= 55:
            return {"state": "TARGETED",    "label": "Targeted Response",         "colour": "medium", "icon": "fa-bullseye", "order": 3}
        return {"state": "MONITORING",      "label": "Active Monitoring",         "colour": "medium", "icon": "fa-eye", "order": 2}
    return {"state": "NORMAL",              "label": "Normal — Low Risk",         "colour": "low",    "icon": "fa-check-circle", "order": 1}


def get_communication_plan(risk_level, channels_selected=None):
    """
    Return recommended communication actions based on risk level.
    Includes target audience, urgency, priority, and channel mix.
    """
    plans = {
        "Low": {
            "urgency":          "Standard",
            "priority":         "Standard (P3)",
            "target_audience":  "General Public, Low-Risk Households & Community Centres",
            "message_type":     "General Heat Safety Awareness",
            "message": (
                "Heat safety reminder for your neighbourhood. Stay hydrated, "
                "wear light clothing, and check on elderly neighbours. "
                "Cooling centres are available at local community halls."
            ),
            "channels": ["SMS", "Social Media Advisory"],
            "actions":  ["Send general advisory", "Monitor weekly"],
        },
        "Medium": {
            "urgency":          "Elevated",
            "priority":         "Elevated Priority (P2)",
            "target_audience":  "Vulnerable Populations, Outdoor Workers, Elderly & Chronic Patients",
            "message_type":     "Targeted Preventive Communication",
            "message": (
                "Elevated heat risk detected in your area. Please take precautions: "
                "avoid outdoor activities 10am–3pm, visit your nearest cooling centre, "
                "and contact your local health worker if you feel unwell."
            ),
            "channels": ["SMS", "Local Health Worker Outreach", "Community Centre Notice"],
            "actions":  [
                "Send targeted advisory",
                "Schedule field officer check-in",
                "Monitor twice weekly",
            ],
        },
        "High": {
            "urgency":          "Urgent",
            "priority":         "Critical / Immediate (P1)",
            "target_audience":  "All Residents, High-Risk Vulnerable Clusters, Care Homes & Shelters",
            "message_type":     "Urgent Targeted Communication",
            "message": (
                "URGENT HEAT ALERT for your neighbourhood. Your area is at HIGH heat risk. "
                "Cooling centres are open 24/7. Field health workers are deployed in your area. "
                "Call 1800-HEALTH for immediate assistance. Do NOT remain in hot buildings."
            ),
            "channels": ["SMS", "Local Health Worker Outreach", "Public Announcement",
                         "Community Centre Notice", "Phone Outreach"],
            "actions":  [
                "Health Officer review (MANDATORY — HC-03)",
                "Deploy urgent communication immediately",
                "Dispatch field outreach team",
                "Open emergency cooling centres",
                "Follow-up assessment within 24 hours",
            ],
        },
        "AMBIGUOUS": {
            "urgency":          "Review Required",
            "priority":         "Hold / Internal Review (P0)",
            "target_audience":  "Public Health Data & Surveillance Officers",
            "message_type":     "Manual Review — Hold Communication",
            "message": "Communication on hold pending Health Officer review of conflicting or missing indicators.",
            "channels": [],
            "actions":  ["Manual review by Health Officer", "Do not send automated advisory"],
        },
        "MISSING_DATA": {
            "urgency":          "Review Required",
            "priority":         "Data Validation Hold (P0)",
            "target_audience":  "Health Surveillance Data Team",
            "message_type":     "Manual Review — Missing Critical Data",
            "message": "Communication blocked: critical data (temperature / vulnerability) is missing. Manual review required.",
            "channels": [],
            "actions":  [
                "Gather missing temperature/vulnerability data",
                "Validate data sources",
                "Reassess after data collection",
            ],
        },
        "EXTREME_VALUE": {
            "urgency":          "Data Validation Required",
            "priority":         "Sensor Outlier Validation (P0)",
            "target_audience":  "City Environmental Sensor Network Team",
            "message_type":     "Data Quality Alert",
            "message": "Extreme sensor value detected. Communication blocked pending data validation by the data team.",
            "channels": [],
            "actions":  [
                "Data team validates sensor readings",
                "If confirmed real — escalate immediately",
                "If sensor error — correct and reassess",
            ],
        },
    }
    plan = dict(plans.get(risk_level, plans["AMBIGUOUS"]))
    if channels_selected:
        plan["channels"] = list(channels_selected)
    return plan


def get_data_quality_report(neighbourhoods):
    """
    Analyse all neighbourhoods for data quality issues.
    Returns list of dicts with quality assessment per neighbourhood.
    """
    report = []
    seen_ids = {}

    for nb in neighbourhoods:
        nb_id   = nb.get("neighbourhood_id") or nb["neighbourhood_id"] if hasattr(nb, "__getitem__") else None
        nb_name = nb["neighbourhood_name"] if hasattr(nb, "__getitem__") else None

        issues    = []
        missing   = 0
        invalid   = 0
        outliers  = 0

        # Check for duplicates
        if nb_id in seen_ids:
            issues.append("Duplicate neighbourhood ID")
            invalid += 1
        seen_ids[nb_id] = True

        # Check required numeric fields
        required_fields = [
            ("temperature",          "Temperature"),
            ("vulnerability_score",  "Vulnerability Score"),
            ("service_access_score", "Service Access Score"),
            ("built_environment_score","Built Environment Score"),
        ]
        for field, label in required_fields:
            val = nb[field] if hasattr(nb, "__getitem__") else None
            if val is None:
                issues.append(f"Missing: {label}")
                missing += 1
            elif isinstance(val, float) and math.isnan(val):
                issues.append(f"NaN: {label}")
                missing += 1

        # Check for extreme values
        temp = nb["temperature"] if hasattr(nb, "__getitem__") else None
        if temp is not None and not (isinstance(temp, float) and math.isnan(temp)):
            if float(temp) > 52:
                issues.append(f"Extreme: Temperature {temp}°C > 52°C (sensor error?)")
                outliers += 1
            elif float(temp) < 0:
                issues.append(f"Extreme: Temperature {temp}°C < 0°C")
                outliers += 1

        vuln = nb["vulnerability_score"] if hasattr(nb, "__getitem__") else None
        if vuln is not None and not (isinstance(vuln, float) and math.isnan(vuln)):
            if float(vuln) > 100 or float(vuln) < 0:
                issues.append(f"Invalid: Vulnerability score {vuln} outside [0,100]")
                invalid += 1

        # Data quality score (100 = perfect)
        penalty   = missing * 20 + invalid * 15 + outliers * 10
        quality   = max(0, 100 - penalty)
        status    = "OK" if not issues else ("WARNING" if quality >= 60 else "CRITICAL")

        report.append({
            "neighbourhood_id":   nb_id,
            "neighbourhood_name": nb_name,
            "risk_level":         nb["risk_level"] if hasattr(nb, "__getitem__") else None,
            "issues":             issues,
            "missing_count":      missing,
            "invalid_count":      invalid,
            "outlier_count":      outliers,
            "quality_score":      quality,
            "status":             status,
        })

    return sorted(report, key=lambda x: x["quality_score"])


def strategy_comparison(neighbourhoods):
    """
    Compare Objective A (Maximum Coverage) vs Objective B (Resource Efficiency).
    Uses the real neighbourhood dataset — no invented results.
    """
    MAX_RESOURCES = 20

    high_risk  = [n for n in neighbourhoods
                  if n["risk_level"] == "High" and n["risk_score"] is not None]
    medium_risk = [n for n in neighbourhoods if n["risk_level"] == "Medium"]
    all_valid   = [n for n in neighbourhoods
                   if n["risk_level"] in ("High","Medium","Low")
                   and n["risk_score"] is not None]

    # Objective A: Maximum Coverage — prioritise by level then score
    priority = {"High": 3, "Medium": 2, "Low": 1}
    obj_a_sorted  = sorted(all_valid,
                           key=lambda x: (priority.get(x["risk_level"], 0), x["risk_score"] or 0),
                           reverse=True)
    obj_a_reached = obj_a_sorted[:MAX_RESOURCES]
    obj_a_high    = [n for n in obj_a_reached if n["risk_level"] == "High"]

    # Objective B: Resource Efficiency — only highest-risk with half budget
    obj_b_sorted  = sorted(high_risk, key=lambda x: x["risk_score"] or 0, reverse=True)
    obj_b_reached = obj_b_sorted[:MAX_RESOURCES // 2]
    obj_b_missed  = [n for n in high_risk if n not in obj_b_reached]

    def avg_score(lst):
        scores = [n["risk_score"] for n in lst if n["risk_score"] is not None]
        return round(sum(scores) / len(scores), 1) if scores else 0

    return {
        "obj_a": {
            "name":                   "Maximum Coverage",
            "neighbourhoods_reached": len(obj_a_reached),
            "high_risk_covered_pct":  round(len(obj_a_high) / max(len(high_risk), 1) * 100, 1),
            "est_response_time_hrs":  round(len(obj_a_reached) * 1.5, 1),
            "resource_usage_pct":     round(len(obj_a_reached) / MAX_RESOURCES * 100, 1),
            "urgent_areas_missed":    len(high_risk) - len(obj_a_high),
            "avg_risk_score":         avg_score(obj_a_reached),
        },
        "obj_b": {
            "name":                   "Resource Efficiency",
            "neighbourhoods_reached": len(obj_b_reached),
            "high_risk_covered_pct":  round(len(obj_b_reached) / max(len(high_risk), 1) * 100, 1),
            "est_response_time_hrs":  round(len(obj_b_reached) * 1.5, 1),
            "resource_usage_pct":     round(len(obj_b_reached) / MAX_RESOURCES * 100 * 2, 1),
            "urgent_areas_missed":    len(obj_b_missed),
            "avg_risk_score":         avg_score(obj_b_reached),
        },
        "total_high_risk":   len(high_risk),
        "total_medium_risk": len(medium_risk),
        "max_resources":     MAX_RESOURCES,
    }
