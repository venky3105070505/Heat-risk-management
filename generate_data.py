"""
generate_data.py
Generates realistic synthetic neighbourhood-level heat-risk data for 60 neighbourhoods.
Saves to neighbourhood_heat_risk.csv.
Run: python generate_data.py
"""

import numpy as np
import pandas as pd
import os

np.random.seed(42)
N = 60

# ── Neighbourhood names ──────────────────────────────────────────────────────
names = [
    "Ashfield", "Bankstown", "Blacktown", "Bondi", "Burwood",
    "Campbelltown", "Canterbury", "Castle Hill", "Chatswood", "Cronulla",
    "Dee Why", "Epping", "Fairfield", "Five Dock", "Granville",
    "Hornsby", "Hurstville", "Kogarah", "Lane Cove", "Leichhardt",
    "Liverpool", "Manly", "Marrickville", "Miranda", "Mosman",
    "Mount Druitt", "Newtown", "North Sydney", "Parramatta", "Penrith",
    "Randwick", "Redfern", "Richmond", "Rockdale", "Ryde",
    "St George", "Strathfield", "Sutherland", "Sydney CBD", "Tamworth",
    "Turramurra", "Ultimo", "Wahroonga", "Warringah", "Waterloo",
    "Wentworthville", "Willoughby", "Windsor", "Wollstonecraft", "Burleigh",
    "Cabramatta", "Doonside", "Edmondson Park", "Glenmore Park", "Ingleburn",
    "Kellyville", "Leumeah", "Minto", "Narellan", "Rooty Hill",
]

neighbourhood_id = [f"NB{str(i+1).zfill(3)}" for i in range(N)]

# ── Geographic coordinates (roughly Sydney metro spread) ─────────────────────
lat_base, lon_base = -33.87, 151.21
latitudes  = lat_base + np.random.uniform(-0.9, 0.9, N)
longitudes = lon_base + np.random.uniform(-0.9, 0.9, N)

# ── Climate indicators ────────────────────────────────────────────────────────
temperature = np.round(np.random.uniform(24, 44, N), 1)      # °C
humidity    = np.round(np.random.uniform(30, 90, N), 1)      # %
# Heat index approximation (Rothfusz equation simplified)
heat_index  = np.round(
    -8.78469475556
    + 1.61139411 * temperature
    + 2.33854883889 * humidity
    - 0.14611605 * temperature * humidity
    - 0.012308094 * temperature**2
    - 0.0164248277778 * humidity**2
    + 0.002211732 * temperature**2 * humidity
    + 0.00072546 * temperature * humidity**2
    - 0.000003582 * temperature**2 * humidity**2,
    1,
)
heat_index = np.clip(heat_index, temperature, 55)  # must be ≥ temperature

# ── Population ────────────────────────────────────────────────────────────────
population           = np.random.randint(8_000, 120_000, N)
elderly_pct          = np.round(np.random.uniform(5, 35, N), 1)
child_pct            = np.round(np.random.uniform(8, 25, N), 1)
low_income_pct       = np.round(np.random.uniform(10, 60, N), 1)
pop_density          = np.round(population / np.random.uniform(1, 12, N), 0)

# ── Built environment ─────────────────────────────────────────────────────────
green_space_pct      = np.round(np.random.uniform(2, 40, N), 1)
building_density     = np.round(np.random.uniform(0.2, 0.95, N), 2)
healthcare_fac       = np.random.randint(0, 12, N)
nearest_hosp_km      = np.round(np.random.uniform(0.5, 25, N), 1)
cooling_centres      = np.random.randint(0, 8, N)
transport_access     = np.random.randint(1, 10, N)  # 1=poor … 10=excellent

# ── Composite scores ─────────────────────────────────────────────────────────
# Service access: higher = better access
service_access_raw = (
    0.30 * (transport_access / 10)
    + 0.25 * np.clip(healthcare_fac / 10, 0, 1)
    + 0.25 * np.clip(cooling_centres / 7, 0, 1)
    + 0.20 * np.clip(1 - nearest_hosp_km / 25, 0, 1)
)
service_access_score = np.round(service_access_raw * 100, 1)

# Vulnerability: higher = more vulnerable
vulnerability_raw = (
    0.40 * (elderly_pct / 35)
    + 0.30 * (low_income_pct / 60)
    + 0.30 * (child_pct / 25)
)
vulnerability_score = np.round(vulnerability_raw * 100, 1)

# Built environment risk: higher = riskier (less green, denser buildings)
built_env_raw = (
    0.50 * building_density
    + 0.50 * (1 - green_space_pct / 40)
)
built_environment_score = np.round(built_env_raw * 100, 1)

# ── Inject 5 edge-case neighbourhoods ────────────────────────────────────────
# Missing temperature (idx 5)
temperature[5]  = np.nan
heat_index[5]   = np.nan
# Very high temp but very low vulnerability (ambiguous – idx 12)
temperature[12]   = 43.5
heat_index[12]    = 48.0
vulnerability_score[12] = 8.0
service_access_score[12] = 85.0
# No cooling centres (idx 20)
cooling_centres[20] = 0
healthcare_fac[20]  = 0
# Extreme outlier temperature (idx 33)
temperature[33] = 55.0
heat_index[33]  = 62.0
# Override-disagreement seed (idx 47) – moderate temp, flagged high previously
temperature[47] = 31.0

# ── Disease and history ───────────────────────────────────────────────────────
infectious_cases        = np.random.randint(0, 150, N)
previous_heat_incidents = np.random.randint(0, 20, N)
comm_reach_pct          = np.round(np.random.uniform(20, 95, N), 1)

# ── Risk scoring (transparent weighted formula) ───────────────────────────────
def normalize(arr, lo=None, hi=None):
    """Min-max normalise, ignoring NaN."""
    lo = np.nanmin(arr) if lo is None else lo
    hi = np.nanmax(arr) if hi is None else hi
    return np.where(np.isnan(arr), np.nan, (arr - lo) / (hi - lo + 1e-9))

temp_norm   = normalize(np.where(temperature > 50, np.nan, temperature))  # extreme → NaN
hi_norm     = normalize(np.where(heat_index > 55, np.nan, heat_index))
vuln_norm   = normalize(vulnerability_score)
built_norm  = normalize(built_environment_score)          # already 0-100
serv_risk   = normalize(100 - service_access_score)       # invert: low access = high risk

# Use whichever of temp / heat_index is available (prefer heat_index)
climate_norm = np.where(~np.isnan(hi_norm), hi_norm, temp_norm)

risk_score_raw = (
    0.35 * climate_norm
    + 0.30 * vuln_norm
    + 0.20 * built_norm
    + 0.15 * serv_risk
)
risk_score = np.round(risk_score_raw * 100, 1)

# Ambiguous flag: high temp (>40) but low vulnerability (<20) → NaN → manual
ambiguous_mask = (
    np.nan_to_num(temperature, nan=0) > 40
) & (vulnerability_score < 20)
risk_score = np.where(ambiguous_mask, np.nan, risk_score)

def risk_level(score):
    if np.isnan(score):
        return "AMBIGUOUS"
    if score < 40:
        return "Low"
    if score < 70:
        return "Medium"
    return "High"

risk_levels = [risk_level(s) for s in risk_score]

# ── Assemble DataFrame ────────────────────────────────────────────────────────
df = pd.DataFrame({
    "neighbourhood_id":          neighbourhood_id,
    "neighbourhood_name":        names,
    "latitude":                  np.round(latitudes, 5),
    "longitude":                 np.round(longitudes, 5),
    "temperature":               temperature,
    "humidity":                  humidity,
    "heat_index":                heat_index,
    "population":                population,
    "elderly_percentage":        elderly_pct,
    "child_percentage":          child_pct,
    "low_income_percentage":     low_income_pct,
    "population_density":        pop_density.astype(int),
    "green_space_percentage":    green_space_pct,
    "building_density":          building_density,
    "healthcare_facilities":     healthcare_fac,
    "nearest_hospital_distance": nearest_hosp_km,
    "cooling_centres":           cooling_centres,
    "public_transport_access":   transport_access,
    "service_access_score":      service_access_score,
    "vulnerability_score":       vulnerability_score,
    "built_environment_score":   built_environment_score,
    "infectious_disease_cases":  infectious_cases,
    "previous_heat_incidents":   previous_heat_incidents,
    "communication_reach_percentage": comm_reach_pct,
    "risk_score":                risk_score,
    "risk_level":                risk_levels,
})

out_path = os.path.join(os.path.dirname(__file__), "neighbourhood_heat_risk.csv")
df.to_csv(out_path, index=False)
print(f"[OK] Saved {len(df)} neighbourhoods -> {out_path}")
print(df["risk_level"].value_counts().to_string())
