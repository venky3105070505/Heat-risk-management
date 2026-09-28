# Neighbourhood Heat-Risk Communication & Response Planner
### Public Health Decision-Support & Surveillance System — City Health Department

---

## 1. Project Overview
The **Neighbourhood Heat-Risk Communication & Response Planner** is a specialized, production-ready public health decision-support system designed for municipal health departments, emergency response coordinators, and epidemiologists. 

Rather than functioning as an automated black-box or clinical diagnosis tool, the application operationalizes a strict **Human-in-the-Loop (HITL)** governance framework. It continuously aggregates micro-climate observations, demographic vulnerabilities, built-environment metrics, and healthcare access indices across urban sectors to deliver actionable risk intelligence, automated operational alerts, priority action queues, targeted communication plans, and structured escalation pipelines.

---

## 2. Problem Statement
Extreme heat events are the deadliest climate-driven natural hazard in urban environments. However, traditional municipal heat mitigation suffers from critical operational flaws:
1. **Generic City-Wide Advisories:** Broadcasting the same generic heat warnings via broadcast television or radio fails to drive protective behavioural change in high-density, low-income, or socially isolated communities.
2. **Hidden Local Vulnerabilities:** Temperature alone does not equal heat disaster. Neighbourhoods with high proportions of elderly residents, infants, pre-existing chronic conditions, poor tree canopy, high building density, and long distances to cooling centres face severe mortality risks even under moderate heat conditions.
3. **Data Quality & Ambiguity Gaps:** Real-world sensor inputs and surveys frequently suffer from missing values, temperature extremes (>50°C), and conflicting indices. Automated systems that silently guess or fail can cause catastrophic response delays.
4. **Lack of Accountable Governance:** Emergency deployments and risk overrides often lack persistent audit logs, creating compliance, medical, and operational liability.

---

## 3. Features & System Capabilities

### A. Executive Dashboard & Operational Intelligence
- **Executive KPI Summary:** Real-time tracking of total monitored neighbourhoods, tier counts (High, Medium, Low), ambiguous/data-quality cases, pending human reviews, open escalation tickets, average communication reach, and city-wide average risk score.
- **Interactive Visualizations (Chart.js):**
  - Risk tier distribution donut.
  - Top 10 highest-risk sector ranking horizontal bar chart.
  - Temperature vs. Risk Score scatter plot.
  - Vulnerability Score vs. Risk Score scatter plot.
  - Service Access Score vs. Risk Score scatter plot.
  - Built Environment Score vs. Risk Score scatter plot.
- **Real-Time Operational Alerts Panel:** Immediate triage cards for critical sectors, pending reviews, active escalations, missing sensor inputs, and failed communications with direct click-through navigation.
- **Priority Actions Today:** Dynamically computed from database state to guide shift briefings without fabricated data.

### B. Global Search & Notification Center
- **Top Navigation Global Search:** Instant debounced search querying neighbourhood names, sector IDs, and risk tiers with live clickable dropdown results.
- **Live Notification Bell:** Unread counter and dropdown drawer summarizing actionable public-health alerts.

### C. Advanced Multi-Criteria Neighbourhood Surveillance
- Multi-dimensional filtering by Risk Level, Risk Score range, Ambient Temperature range, Vulnerability Index, Healthcare Access, Data Quality flags, Human Review state, and Escalation status.
- Real-time search and multi-column sorting (Risk Score, Temperature, Vulnerability, Total Population).
- Filtered count indicator and direct CSV dataset export.

### D. Comprehensive 7-Section Sector Dossier
Each neighbourhood detail view provides an exhaustive operational breakdown:
1. **Risk Summary:** Comprehensive score, risk level badge, heat index, and core composite dimensions.
2. **Risk Contribution Breakdown:** Progress bars and percentage weights indicating exact point contributions from Climate (35%), Vulnerability (30%), Built Environment (20%), and Service Access (15%).
3. **Population & Vulnerability:** Population count, elderly percentage, child percentage, low-income percentage, and population density.
4. **Health & Infrastructure:** Healthcare facilities count, distance to nearest emergency hospital, cooling centres count, transit access score, previous heat incident records, and active infectious disease metrics.
5. **Communication Readiness:** Reach percentage, recommended primary and secondary delivery channels, dispatch history, and failure logs.
6. **Human Decision Section:** Review status, assigned reviewer, review notes, and historical override audit trail.
7. **Escalation Status:** Current ticket state, assigned officer, resolution timestamp, and mandatory sign-off notes.
8. **Observation & Trend History:** Supports future multi-epoch surveillance records (`risk_snapshots`) with zero synthetic historical fabrication.

### E. Interactive Risk Map (Leaflet.js)
- Color-coded circular markers for High (red), Medium (orange), Low (green), and Ambiguous/Flagged (purple) sectors.
- Visual halos distinguishing active escalation tickets and pending human review queues.
- Real-time Leaflet heat-layer toggle (`leaflet.heat.js`) for spatial thermal risk density visualization.
- Multi-filter chips (All, High Risk Only, Needs Review, Open Escalations) and rich interactive popup inspection cards.

### F. Human-in-the-Loop & Risk Override Governance
- Hard constraint automated enforcement: any sector classified as High Risk, Ambiguous, Missing Data, or Extreme Value is automatically gated into **Human Review Required** status.
- Review officers can **Approve**, **Modify**, **Request Information**, or **Escalate**.
- Authorised overrides (restricted to Health Officers and Administrators) enforce mandatory written justification before submission, log previous vs. new classifications, and record the user ID, timestamp, and client IP without ever deleting the original baseline assessment.

### G. 6-Stage Operational Escalation Pipeline
Structured incident escalation following city emergency protocols:
$$\text{NORMAL} \longrightarrow \text{MONITORING} \longrightarrow \text{TARGETED RESPONSE} \longrightarrow \text{HUMAN OFFICER REVIEW} \longrightarrow \text{HIGH RISK ESCALATION} \longrightarrow \text{IMMEDIATE ESCALATION}$$
- Officer assignment, state transitions, and resolution requiring mandatory sign-off notes.

### H. Multi-Channel Communication Planner
- Automated message drafting tailored to risk tiers with clear audience targeting and priority classification.
- Channel selection across: SMS Alerts, Local Health Worker Outreach, Public Address Announcements, Community Centre Notices, Social Media Advisories, and Phone Outreach.
- Confirmation dispatch modal with Sent, Pending, and Failed status tracking.

### I. Data Quality Center & Anomaly Detection
- Automatic detection of missing sensor records, conflicting metrics, and extreme outliers (>50°C).
- Transparent remediation table detailing: **What is wrong**, **Why it matters**, and **Recommended human action**.

### J. Dedicated Analytics & Strategy Comparison
- Empirical ranking of highest-risk sectors, vulnerability hotspots, and healthcare deserts.
- Multi-objective comparison (Generic City-Wide Broadcasting vs. High-Risk Targeted Response) with radar and comparative bar charts.

### K. Role-Based Access Control (RBAC) & User Management
- Administrator-only User Management portal: view registered staff, search by name/email, filter by role, activate/deactivate accounts, and inspect last-active timestamps without exposing password hashes.
- Enforced route protection across Administrator, Health Officer, and Field Officer roles.

### L. Audit Logging & Compliance Export
- Comprehensive logging of logins, logouts, reviews, overrides, escalations, communications, and account state modifications.
- CSV export for High-Risk areas, All Neighbourhoods, Review Queue, Communications History, Audit Logs, and Data Quality anomalies.

### M. UI/UX Excellence & Dark Mode
- Polished public-health theme using Inter typography, subtle micro-interactions, responsive mobile drawer navigation, and a persistent dark mode toggle (`localStorage`).
- Custom branded 404, 403, and 500 error pages.

---

## 4. Architecture
The application is structured as a modular, lightweight 3-tier web architecture designed for public-sector stability and high maintainability:

```
┌────────────────────────────────────────────────────────────────────────┐
│                        Presentation Layer (UI/UX)                      │
│   • Jinja2 Templates (HTML5 + Semantic Structure)                      │
│   • Custom Vanilla CSS Design System + Dark Theme Variable Engine      │
│   • Bootstrap 5.3 + FontAwesome 6 + Chart.js 4 + Leaflet.js            │
│   • Asynchronous JavaScript (Global Search, Dark Mode, Map Rendering)   │
└────────────────────────────────────┬───────────────────────────────────┘
                                     │ HTTP / REST / JSON
┌────────────────────────────────────▼───────────────────────────────────┐
│                    Application Layer (Flask Controller)                │
│   • app.py: RBAC Decorators, Session Handling, Route Controllers       │
│   • risk_engine.py: Deterministic Risk Formula, Constraint Engine       │
│   • Error Handlers (404, 403, 500) & Global Context Processors         │
└────────────────────────────────────┬───────────────────────────────────┘
                                     │ Parameterized SQL (WAL Mode)
┌────────────────────────────────────▼───────────────────────────────────┐
│                         Data Layer (SQLite & CSV)                      │
│   • SQLite Database (heat_risk.db) with Indexing & Foreign Keys        │
│   • database.py: Safe Migrations, Audit Logging, Snapshot Logging      │
│   • neighbourhood_heat_risk.csv: Ground-truth municipal dataset        │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 5. Technology Stack
- **Backend Framework:** Python 3.10+ / Flask 3.0+
- **Database:** SQLite 3 with Write-Ahead Logging (WAL) and foreign key constraints
- **Frontend / Styling:** HTML5, Vanilla CSS with custom tokens and CSS custom properties (Dark/Light mode)
- **UI Frameworks:** Bootstrap 5.3.3 (responsive grid and utilities), Font Awesome 6.5.1
- **Visualization:** Chart.js 4.4.3 (Donut, Bar, Scatter, Radar)
- **Mapping & Spatial Analysis:** Leaflet.js 1.9.4 & Leaflet.heat 0.2.0 (OpenStreetMap tiles)
- **Security & Authentication:** Werkzeug `generate_password_hash` / `check_password_hash` (scrypt), secure HTTP session management
- **Testing:** Pytest 9.1.1 (70 automated unit, integration, and security tests)

---

## 6. Database Structure
The application uses SQLite (`heat_risk.db`) with relational integrity and performance indexes:

### Tables Overview
1. `users`: System accounts with role (`Administrator`, `Health Officer`, `Field Officer`), password hash, `is_active` flag, and `last_active` timestamp.
2. `neighbourhoods`: 60 sectors with spatial coordinates, micro-climate metrics, vulnerability factors, built environment scores, healthcare infrastructure metrics, and calculated risk tier.
3. `risk_assessments`: Deterministic audit record of formula steps, constraint outputs, and human review flags.
4. `human_reviews`: Queue entries for flagged sectors with `status` (`Pending`, `Approved`, `Modified`, `Escalated`, `Info Requested`), `notes`, `reviewer_id`, and `priority`.
5. `escalations`: Multi-stage incident tickets with `current_state` (6-stage pipeline), `escalation_type`, `assigned_to`, and `resolution_notes`.
6. `overrides`: Permanent record of user-initiated risk changes tracking `original_level`, `new_level`, `reason`, `overridden_by`, and `overridden_at`.
7. `communications`: Dispatch history storing `neighbourhood_id`, `message_type`, `channels`, `message_text`, `target_audience`, `priority`, `status` (`Sent`, `Pending`, `Failed`), and `failure_reason`.
8. `risk_snapshots`: Multi-epoch observation store supporting longitudinal trend analysis with `recorded_at`, `temperature`, `heat_index`, `risk_score`, and `notes`.
9. `audit_logs`: Immutable security and operations log recording `user_id`, `username`, `action`, `entity_type`, `entity_id`, `details`, `ip_address`, and `created_at`.
10. `stakeholder_feedback`: Feedback evaluations and Likert scores from field officers and clinicians.

---

## 7. Risk Calculation Explanation
The risk calculation is completely transparent, deterministic, and explainable to clinical and public health stakeholders.

### Normalization
All component dimensions are normalized to a scale of $0.0 - 1.0$:
- **Climate Normalization:**
  $$\text{Climate Score} = \min\left(1.0, \max\left(0.0, \frac{\text{Heat Index} - 25.0}{25.0}\right)\right)$$
- **Vulnerability Normalization:**
  $$\text{Vuln Score} = \frac{\text{Vulnerability Score}}{100.0}$$
- **Built Environment Risk:**
  $$\text{Built Score} = \frac{\text{Built Environment Score}}{100.0}$$
- **Service Access Risk (Inverted):** Low access corresponds to high risk:
  $$\text{Service Risk} = 1.0 - \frac{\text{Service Access Score}}{100.0}$$

### Composite Risk Formula
$$\text{Composite Risk Score} = \left(0.35 \times \text{Climate} + 0.30 \times \text{Vuln} + 0.20 \times \text{Built} + 0.15 \times \text{Service}\right) \times 100$$

### Classification Thresholds
- **High Risk:** $\ge 70.0$
- **Medium Risk:** $40.0 - 69.9$
- **Low Risk:** $< 40.0$
- **Ambiguous / Data Quality:** Missing temperature, missing vulnerability score, or extreme temperature anomaly ($> 50.0^\circ\text{C}$).

---

## 8. Human-in-the-Loop (HITL) Workflow
Automated systems in public health must never trigger unilateral emergency deployments or silence anomalies without human oversight.

```
┌─────────────────────────────────┐
│ Sector Ingestion & Risk Scoring │
└────────────────┬────────────────┘
                 │
                 ▼
     Is Score ≥ 70 OR Flagged?
       ├── No  ───► Standard Monitoring Tier
       └── Yes ───► Flag: "Human Review Required"
                         │
                         ▼
             ┌───────────────────────┐
             │ Review Queue Assigned │
             └───────────┬───────────┘
                         │
        ┌────────────────┼────────────────┬────────────────┐
        ▼                ▼                ▼                ▼
   [ Approve ]      [ Modify ]      [ Request Info ]  [ Escalate ]
        │                │                │                │
        ▼                ▼                ▼                ▼
   Unlocks Comms   Logs Override    Alerts Field    Creates Ticket
   Dispatch        to Audit Trail   Surveillance    in Pipeline
```

---

## 9. Escalation Workflow
When a sector experiences extreme heat spikes or critical vulnerability thresholds, it enters a structured 6-stage operational pipeline:

1. **NORMAL:** Routine surveillance, standard seasonal alerts.
2. **MONITORING:** Elevated thermal index; increased polling of local cooling centres.
3. **TARGETED RESPONSE:** Medium-risk sector with high elderly or low-income density; localized mobile hydration units planned.
4. **HUMAN OFFICER REVIEW:** Mandatory clinical and environmental review before mass broadcasts.
5. **HIGH RISK ESCALATION:** Severe heat conditions; active health officer coordination and cooling shelter activation.
6. **IMMEDIATE ESCALATION:** Emergency conditions (Risk Score $\ge 90$ or severe cascading infrastructure failure); immediate city executive response.

---

## 10. Communication Workflow
The communication planner translates analytical risk into clear, protective community action:
1. **Advisory Generation:** Generates targeted guidance based on risk level and demographic factors (e.g., hydration advisories for elderly care centres, cooling centre operating hours).
2. **Channel Selection:** Allows selecting channels (SMS Alert, Local Health Workers, Public Announcements, Community Centres, Social Media, Phone Outreach).
3. **Dispatch Review & Confirmation:** A confirmation dialog prevents accidental broadcast dispatches.
4. **Status Lifecycle:** Tracks dispatches as **Sent**, **Pending**, or **Failed**, logging any transmission errors.

---

## 11. User Roles & Access Matrix

| Feature / Page | Administrator | Health Officer | Field Officer |
|---|:---:|:---:|:---:|
| Executive Dashboard & Analytics | Full Access | Full Access | Full Access |
| Neighbourhood Surveillance & Search | Full Access | Full Access | Full Access |
| Interactive Risk Map & Heatmap | Full Access | Full Access | Full Access |
| Review Queue Operations | Full Access | Full Access | View Assigned |
| Risk Overrides (with written reason) | Yes | Yes | Denied |
| Escalation Ticket State Updates | Yes | Yes | View Only |
| Escalation Ticket Resolution | Yes | Yes | Denied |
| Communication Planning & Dispatch | Yes | Yes | Field Channels |
| Data Quality Center | Full Access | Full Access | View Only |
| Audit Log Inspection & Export | Full Access | View Only | Denied |
| User Management (Activate/Deactivate) | Yes | Denied | Denied |

---

## 12. How to Install
Ensure Python 3.10 or higher is installed on your system.

```bash
# 1. Clone repository and navigate to project directory
cd heat_risk_planner

# 2. (Optional) Create and activate a virtual environment
python -m venv venv
# On Windows:
.\venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate

# 3. Install required packages
pip install -r requirements.txt
```

---

## 13. How to Run
```bash
# 1. Generate or verify synthetic dataset
python generate_data.py

# 2. Launch the Flask application
python app.py
```
The application will start on **`http://127.0.0.1:5000`** and open automatically in your default browser.

### Seed User Accounts
Initial administrative and officer accounts are automatically created by `init_db()`:
- **Administrator:** `admin@healthdept.local` / `Admin@2026!`
- **Health Officer:** `health@healthdept.local` / `Health@2026!`
- **Field Officer:** `field@healthdept.local` / `Field@2026!`

*(Note: Users can also register new staff accounts on the `/signup` portal).*

---

## 14. How to Test
The project includes a comprehensive automated test suite with **70 tests** covering authentication, RBAC authorization, mathematical risk scoring, hard constraints, escalation workflows, communication planning, SQLite migrations, snapshots, and custom error pages.

```bash
# Run the entire test suite with verbose output
python -m pytest test_app.py -v
```

---

## 15. Project Folder Structure
```
heat_risk_planner/
├── app.py                         ← Flask application controller, routes & decorators
├── database.py                    ← SQLite schema, migrations, indexing & query helpers
├── risk_engine.py                 ← Deterministic risk scoring & constraint logic
├── generate_data.py               ← Dataset generation script (60 urban sectors)
├── neighbourhood_heat_risk.csv    ← Master municipal dataset
├── requirements.txt               ← Python dependencies
├── README.md                      ← Comprehensive documentation (this file)
├── test_app.py                    ← 70 unit and integration tests (Pytest)
├── templates/                     ← Jinja2 HTML templates
│   ├── base.html                  ← Master layout (Top navigation, global search, notifications, dark mode)
│   ├── dashboard.html             ← Executive summary, operational alerts, actions today, 6 charts
│   ├── neighbourhoods.html        ← Advanced multi-criteria filtering, search, sorting & CSV export
│   ├── neighbourhood_detail.html  ← 7-section dossier, contribution breakdown & trend snapshots
│   ├── map.html                   ← Leaflet interactive risk map, filter chips & heat-layer
│   ├── review_queue.html          ← Human review queue (Approve, Modify, Escalate)
│   ├── escalation.html            ← 6-stage operational escalation pipeline & resolution modal
│   ├── communication.html         ← Multi-channel communication planner & dispatch logs
│   ├── data_quality.html          ← Anomaly detection & remediation advice table
│   ├── analytics.html             ← Dedicated epidemiological & spatial risk insights
│   ├── users.html                 ← Administrator-only user management portal
│   ├── audit.html                 ← Filterable security and operational audit logs
│   ├── strategy.html              ← Strategy comparison (Generic vs. Targeted Response)
│   ├── journeys.html              ← Case study walkthroughs of individual sectors
│   ├── experiment.html            ← Empirical evaluation results
│   ├── failures.html              ← Failure mode analysis & mitigation register
│   ├── constraints.html           ← Hard and soft constraint configuration catalog
│   ├── feedback.html              ← Stakeholder evaluation survey & Likert radar
│   ├── documentation.html         ← In-app operational reference guide
│   ├── login.html                 ← Secure authentication portal
│   ├── signup.html                ← Staff account registration portal
│   ├── 404.html                   ← Custom branded 404 error page
│   ├── 403.html                   ← Custom branded 403 forbidden page
│   └── 500.html                   ← Custom branded 500 server error page
└── static/
    ├── css/
    │   └── style.css              ← Design system, responsive rules & Dark Mode CSS engine
    └── js/
        └── app.js                 ← Chart.js helpers, theme switcher, global search & mobile drawer
```

---

## 16. Future Improvements
For subsequent enterprise scaling and live operational deployment, the following enhancements are planned:
1. **Live IoT Weather Sensor Integration:** Direct ingest pipelines connected via MQTT or REST to municipal automated weather stations (AWS) for minute-by-minute heat index updates.
2. **Satellite Thermal Infrared Ingestion:** Ingesting high-resolution Landsat-9 or Sentinel-2 thermal band data to automatically calculate micro-scale Urban Heat Island (UHI) surface temperatures.
3. **Automated SMS Gateway (Twilio / Webhook):** Connecting the communication planner prototype to live emergency broadcast gateways with real-time delivery receipt callbacks.
4. **Predictive Heatwave Forecast Modeling:** Coupling the deterministic risk formula with 72-hour numerical weather prediction forecasts (NWP) to trigger preventative early-warning alerts before temperatures peak.
5. **Offline Mobile Field Client (PWA):** Progressive Web App caching enabling field outreach workers to log cooling shelter checks in network-blind basement or dense building zones.
