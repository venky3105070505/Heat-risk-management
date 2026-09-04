# Neighbourhood Heat-Risk Communication & Response Planner

## Problem Statement
Current city-wide public health advisories are too generic and fail to drive behavioural change in specific high-risk neighbourhoods. Seasonal heat events disproportionately affect elderly, low-income, and high-density communities — yet all areas receive the same communication.

## Project Objective
A **decision-support system** (not a clinical diagnosis tool) that identifies neighbourhood-level heat risk using temperature, built-environment, service-access, and aggregate vulnerability indicators, then recommends timely, understandable communication and response actions.

## Architecture
| Layer | Technology |
|-------|-----------|
| Frontend | HTML5, Bootstrap 5, Chart.js 4, Leaflet.js |
| Backend | Python 3.10+ / Flask 3.0 |
| Database | SQLite (sqlite3, no ORM) |
| Data | Pandas + NumPy |
| Risk Engine | Transparent weighted formula |
| Map | OpenStreetMap (no API key required) |

## Project Structure
```
heat_risk_planner/
├── app.py                    ← Flask app, all 16 routes
├── database.py               ← Schema, seed, audit helper
├── risk_engine.py            ← Transparent risk scoring + constraints
├── generate_data.py          ← Synthetic dataset (60 neighbourhoods)
├── requirements.txt
├── README.md
├── neighbourhood_heat_risk.csv
├── experiment.ipynb
├── templates/                ← 16 Jinja2 HTML templates
└── static/css/ js/           ← Design system + chart helpers
```

## Dataset Fields (60 neighbourhoods)
- neighbourhood_id, neighbourhood_name, latitude, longitude
- temperature, humidity, heat_index
- population, elderly_percentage, child_percentage, low_income_percentage, population_density
- green_space_percentage, building_density
- healthcare_facilities, nearest_hospital_distance, cooling_centres, public_transport_access
- service_access_score, vulnerability_score, built_environment_score
- infectious_disease_cases, previous_heat_incidents, communication_reach_percentage
- risk_score, risk_level

## Risk Calculation (Transparent)
```
Heat Risk Score =
  (Climate/Heat Index normalised) × 0.35
+ (Vulnerability Score normalised) × 0.30
+ (Built Environment Risk normalised) × 0.20
+ (Service Access Risk normalised) × 0.15
× 100

Thresholds: 0–39 = Low | 40–69 = Medium | 70–100 = High
```
Every component contribution is displayed on each neighbourhood detail page.

## Hard Constraints
| ID | Constraint |
|----|-----------|
| HC-01 | Aggregate neighbourhood data only |
| HC-02 | High-risk cannot be auto-closed |
| HC-03 | High-risk requires human review |
| HC-04 | Emergency cases must be escalated |
| HC-05 | Only Health Officers/Admins can override |
| HC-06 | Override requires written reason |
| HC-07 | Every override is permanently logged |
| HC-08 | Missing temperature/vulnerability blocks auto-classification |

## Soft Constraints (Configurable)
- SC-01: Prioritise high-vulnerability neighbourhoods
- SC-02: Prioritise poor healthcare access
- SC-03: Minimise response time
- SC-04: Minimise field-team workload
- SC-05: Maximise high-risk areas reached
- SC-06: Prefer simple understandable language

## Human Review
Every High-risk and AMBIGUOUS classification creates a Review Queue entry. Officers can Approve, Modify, Escalate, or Request More Information.

## Override Mechanism
Health Officers and Administrators can override risk levels. Override requires mandatory written reason. Stored in `overrides` table and `audit_logs` simultaneously.

## Escalation Logic
1. Low → Standard advisory + monitoring
2. Medium → Targeted advisory + field officer review
3. High → Health Officer review (mandatory) + urgent comms + field response
4. Ambiguous → Manual review → Health Officer decision
5. Emergency (score ≥ 90) → Auto-escalate to Senior Health Officer / Admin

## Failure Cases
| ID | Failure | Response |
|----|---------|----------|
| FC-01 | Missing temperature | Block auto-classification, manual review |
| FC-02 | Conflicting indicators | Mark AMBIGUOUS, human review |
| FC-03 | No cooling/healthcare | Escalate, recommend alternate services |
| FC-04 | Extreme outlier (>52°C) | Flag EXTREME_VALUE, data validation |
| FC-05 | Override disagreement | Lock further overrides, Admin resolution |

## Setup Instructions
```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Generate synthetic dataset
python generate_data.py

# 3. Start the application (auto-inits database)
python app.py
```
Open: http://127.0.0.1:5000

## Demo Credentials
| Role | Username | Password |
|------|----------|----------|
| Administrator | admin | admin123 |
| Health Officer | health_officer | health123 |
| Field Officer | field_officer | field123 |

## Application Workflow
```
Synthetic Data → Data Validation → Risk Scoring → Risk Classification
→ Communication Recommendation → Human Review → Authorised Override
→ Escalation → Communication/Field Action → Outcome Tracking → Experiment Metrics
```

## Pages
| Page | Route |
|------|-------|
| Login | /login |
| Dashboard | /dashboard |
| Neighbourhoods | /neighbourhoods |
| Neighbourhood Detail | /neighbourhood/<id> |
| Risk Map | /map |
| Communication Planner | /communication |
| Review Queue | /review-queue |
| Escalation Workflow | /escalation |
| Strategy Comparison | /strategy |
| Case Journeys | /journeys |
| Experiment Results | /experiment |
| Failure Mode Analysis | /failures |
| Constraints | /constraints |
| Audit Log | /audit |
| Stakeholder Feedback | /feedback |
| Documentation | /documentation |

## Important Notes
- This is a **decision-support system only** — it does not replace health department workflow
- No clinical diagnoses are made
- No real patient information is stored or processed
- All risk scores are explainable and challengeable
- Human review points are explicitly identified at every critical decision
