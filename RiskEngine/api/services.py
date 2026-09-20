"""
Data access for the API layer.

Reads two sources:
  - outputs/*.json  — computed results from the pipeline (FAIR, optimization,
    compliance, attack graph). Authoritative for anything financial.
  - data/*.csv      — source telemetry, for the row-level views (vulnerability
    table, threat intel) that the pipeline aggregates away.

CSVs are cached and invalidated by file mtime so an ingest is picked up without
a restart, and a 30k-row table isn't re-parsed on every request.
"""

from __future__ import annotations

import json
import math
import threading
from datetime import datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "outputs"

_cache: Dict[str, Any] = {}
_cache_lock = threading.Lock()


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------

def load_json(name: str) -> Dict:
    path = OUTPUT_DIR / name
    if not path.exists():
        return {}
    key = f"json:{name}"
    stamp = path.stat().st_mtime
    with _cache_lock:
        hit = _cache.get(key)
        if hit and hit[0] == stamp:
            return hit[1]
    try:
        with open(path) as f:
            payload = json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}
    with _cache_lock:
        _cache[key] = (stamp, payload)
    return payload


def load_csv(name: str, usecols: Optional[List[str]] = None) -> pd.DataFrame:
    path = DATA_DIR / f"{name}.csv"
    if not path.exists():
        return pd.DataFrame()
    key = f"csv:{name}"
    stamp = path.stat().st_mtime
    with _cache_lock:
        hit = _cache.get(key)
        if hit and hit[0] == stamp:
            return hit[1]
    df = pd.read_csv(path, usecols=usecols)
    with _cache_lock:
        _cache[key] = (stamp, df)
    return df


def graph_data() -> Dict:
    return load_json("graph_data.json")


def pipeline_has_run() -> bool:
    return bool(graph_data())


# ---------------------------------------------------------------------------
# Shared derivations
# ---------------------------------------------------------------------------

CRITICALITY_LABEL_SCORE = {"Critical": 5, "High": 4, "Medium": 3, "Low": 2}


def numeric_criticality(series) -> "pd.Series":
    """
    assets.csv stores asset_criticality as a text label (Critical/High/Medium/
    Low), not a number. Anywhere that needs to average or sort by it must go
    through this rather than calling .mean()/.sort_values() on the raw column,
    which raises (categorical) or sorts alphabetically (wrong order).
    """
    return series.map(CRITICALITY_LABEL_SCORE).fillna(3)


def risk_level_from_score(score: float) -> str:
    """Single definition of the score→band mapping, used everywhere."""
    if score >= 75:
        return "Critical"
    if score >= 50:
        return "High"
    if score >= 25:
        return "Medium"
    return "Low"


def risk_level_from_cvss(cvss: float) -> str:
    if cvss >= 9.0:
        return "Critical"
    if cvss >= 7.0:
        return "High"
    if cvss >= 4.0:
        return "Medium"
    return "Low"


def _safe(value, default=0.0) -> float:
    try:
        f = float(value)
        return default if (math.isnan(f) or math.isinf(f)) else f
    except (TypeError, ValueError):
        return default


def executive_summary() -> Dict:
    return graph_data().get("executive_summary", {}) or {}


def overall_risk_score() -> float:
    """
    Enterprise risk score on 0-100.

    Anchored to exposure relative to the organisation's own revenue rather than
    an absolute rupee figure, so the score stays comparable as the estate grows.
    Falls back to a control-effectiveness proxy when revenue is unavailable.
    """
    summary = executive_summary()

    # The engine computes and persists this score (src/risk_history.py) because
    # the trend chart plots the same series. Recomputing it here would let the
    # headline number and its own trend line disagree.
    persisted = summary.get("enterprise_risk_score")
    if persisted is not None:
        return round(float(persisted), 1)

    eal = _safe(summary.get("total_expected_loss"))
    orgs = graph_data().get("business_unit_risk", {}).get("by_organization", [])

    revenue = sum(_safe(o.get("annual_revenue")) for o in orgs)
    if revenue > 0 and eal > 0:
        ratio = eal / revenue
        # 0% of revenue -> 0, 20%+ of revenue -> 100
        return round(min(100.0, (ratio / 0.20) * 100), 1)

    controls = load_csv("security_controls")
    if not controls.empty and "effectiveness_score" in controls:
        return round(min(100.0, (1 - controls["effectiveness_score"].mean()) * 100), 1)
    return 0.0


def _synthetic_trend(current: float, points: int = 12, drift: float = 0.06) -> List[Dict]:
    """
    Back-cast a monthly trend from the current value.

    The engine keeps no historical snapshots yet, so this is a smooth
    reconstruction rather than measured history. Callers surface it as
    'modelled', never as recorded data.
    """
    if current <= 0:
        return []
    out = []
    today = datetime.now()
    for i in range(points - 1, -1, -1):
        month = today - timedelta(days=30 * i)
        # Older points sit progressively higher; risk trends down as controls mature.
        factor = 1 + (drift * i / points) * (1 + 0.25 * math.sin(i * 1.3))
        out.append({"date": month.strftime("%Y-%m"), "value": round(current * factor, 2)})
    return out


def risk_history() -> List[Dict]:
    """Recorded per-run snapshots written by src/risk_history.py."""
    payload = load_json("risk_history.json")
    return payload if isinstance(payload, list) else []


def trend_is_measured() -> bool:
    """True once at least two real snapshots exist; until then trends are modelled."""
    return len(risk_history()) >= 2


def risk_trend(points: int = 12) -> List[Dict]:
    history = risk_history()
    if len(history) >= 2:
        return [
            {"date": h.get("date"), "value": h.get("enterprise_risk_score", 0)}
            for h in history[-points:]
        ]
    return _synthetic_trend(overall_risk_score(), points, drift=0.10)


def exposure_trend(points: int = 12) -> List[Dict]:
    history = risk_history()
    if len(history) >= 2:
        return [
            {"date": h.get("date"), "value": h.get("expected_annual_loss", 0)}
            for h in history[-points:]
        ]
    return _synthetic_trend(_safe(executive_summary().get("total_expected_loss")), points, drift=0.08)


# ---------------------------------------------------------------------------
# Remediation backlog
# ---------------------------------------------------------------------------

def remediation() -> Dict:
    """Prioritized actions + backlog health, produced by src/remediation.py."""
    return graph_data().get("remediation", {}) or {}


def remediation_recommendations(limit: int = 25) -> List[Dict]:
    return remediation().get("top_recommendations", [])[:limit]


def remediation_backlog() -> Dict:
    return remediation().get("backlog", {})


# ---------------------------------------------------------------------------
# Vulnerabilities
# ---------------------------------------------------------------------------

_VULN_COLS = [
    "vulnerability_id", "asset_id", "cve_id", "vulnerability_type", "cvss_score",
    "severity", "known_exploited", "exploit_available", "attack_vector",
    "affected_service", "patch_available", "remediation_status",
    "vulnerability_risk_score", "vulnerability_age_days",
]


def vulnerabilities() -> pd.DataFrame:
    df = load_csv("vulnerabilities")
    if df.empty:
        return df
    cols = [c for c in _VULN_COLS if c in df.columns]
    out = df[cols].copy()

    for flag in ("known_exploited", "exploit_available", "patch_available"):
        if flag in out.columns:
            out[flag] = out[flag].astype(str).str.strip().str.lower().isin(["true", "1", "yes"])

    if "cvss_score" in out.columns:
        out["risk_level"] = out["cvss_score"].apply(risk_level_from_cvss)

    # Source data carries no vendor; affected_service is the closest analogue and
    # stands in as product until NVD enrichment fills both properly.
    out["product"] = out.get("affected_service")
    out["vendor"] = None

    if "vulnerability_age_days" in out.columns:
        out["date_added"] = (
            pd.Timestamp.now().normalize()
            - pd.to_timedelta(out["vulnerability_age_days"].fillna(0), unit="D")
        ).dt.strftime("%Y-%m-%d")

    out["description"] = out.apply(
        lambda r: f"{r.get('vulnerability_type', 'Vulnerability')} in "
                  f"{r.get('affected_service', 'unknown service')} "
                  f"(CVSS {r.get('cvss_score', 'n/a')})",
        axis=1,
    )
    return out


def critical_vulnerability_count() -> int:
    df = vulnerabilities()
    if df.empty or "severity" not in df.columns:
        return 0
    return int((df["severity"] == "Critical").sum())


def severity_distribution() -> Dict[str, int]:
    df = vulnerabilities()
    if df.empty or "severity" not in df.columns:
        return {"critical": 0, "high": 0, "medium": 0, "low": 0}
    counts = df["severity"].value_counts()
    return {
        "critical": int(counts.get("Critical", 0)),
        "high": int(counts.get("High", 0)),
        "medium": int(counts.get("Medium", 0)),
        "low": int(counts.get("Low", 0)),
    }


# ---------------------------------------------------------------------------
# Threats
# ---------------------------------------------------------------------------

def threats() -> pd.DataFrame:
    df = load_csv("threat_intelligence")
    if df.empty:
        return df
    out = df.copy()
    for flag in ("campaign_active", "ransomware_indicator"):
        if flag in out.columns:
            out[flag] = out[flag].astype(str).str.strip().str.lower().isin(["true", "1", "yes"])
    return out


def active_high_risk_threats() -> int:
    df = threats()
    if df.empty:
        return 0
    mask = pd.Series(True, index=df.index)
    if "campaign_active" in df.columns:
        mask &= df["campaign_active"]
    if "severity" in df.columns:
        mask &= df["severity"].isin(["Critical", "High"])
    return int(mask.sum())


# ---------------------------------------------------------------------------
# Controls
# ---------------------------------------------------------------------------

def controls() -> pd.DataFrame:
    return load_csv("security_controls")


def investment_options() -> pd.DataFrame:
    return load_csv("investment_options")


def compliance_report() -> Dict:
    return load_json("compliance_report.json")
