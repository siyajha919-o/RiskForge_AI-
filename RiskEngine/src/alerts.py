"""
Alert evaluation.

Rules are checked against the computed outputs after each pipeline run, and the
results are persisted so an alert survives a restart and can be acknowledged.
This is deliberately a small JSON store rather than a database, matching how
audit_log.jsonl and users.json already work in this engine.

An alert has a stable `id` derived from its rule and subject, so re-running the
pipeline updates the existing alert rather than producing a duplicate — and an
acknowledgement is not lost just because the numbers were recomputed.
"""

from __future__ import annotations

import json
import hashlib
import os
import threading
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

SEVERITY_ORDER = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _alert_id(rule: str, subject: str = "") -> str:
    return hashlib.sha256(f"{rule}|{subject}".encode()).hexdigest()[:16]


class AlertStore:
    """Reads and writes the alert list, preserving acknowledgements."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self._lock = threading.Lock()

    def _read(self) -> List[Dict]:
        if not self.path.exists():
            return []
        try:
            with open(self.path) as f:
                payload = json.load(f)
            return payload if isinstance(payload, list) else []
        except (json.JSONDecodeError, OSError):
            return []

    def _write(self, alerts: List[Dict]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        with open(tmp, "w") as f:
            json.dump(alerts, f, indent=2)
        os.replace(tmp, self.path)

    def list(self, include_acknowledged: bool = True) -> List[Dict]:
        alerts = self._read()
        if not include_acknowledged:
            alerts = [a for a in alerts if not a.get("acknowledged")]
        return sorted(
            alerts,
            key=lambda a: (SEVERITY_ORDER.get(a.get("severity"), 9),
                           a.get("last_seen", "")),
        )

    def acknowledge(self, alert_id: str, actor: str) -> Optional[Dict]:
        with self._lock:
            alerts = self._read()
            for a in alerts:
                if a["id"] == alert_id:
                    a["acknowledged"] = True
                    a["acknowledged_by"] = actor
                    a["acknowledged_at"] = _now()
                    self._write(alerts)
                    return a
            return None

    def sync(self, evaluated: List[Dict]) -> List[Dict]:
        """
        Merges freshly evaluated alerts over the stored ones.

        A still-firing alert keeps its acknowledgement and first_seen; one that
        no longer fires is dropped. Acknowledging is therefore 'I have seen this
        value', and a materially changed value re-raises the alert.
        """
        with self._lock:
            existing = {a["id"]: a for a in self._read()}
            merged = []
            for alert in evaluated:
                prior = existing.get(alert["id"])
                if prior:
                    alert["first_seen"] = prior.get("first_seen", _now())
                    # Keep the acknowledgement only while the figure is unchanged.
                    if prior.get("acknowledged") and prior.get("value") == alert.get("value"):
                        alert["acknowledged"] = True
                        alert["acknowledged_by"] = prior.get("acknowledged_by")
                        alert["acknowledged_at"] = prior.get("acknowledged_at")
                else:
                    alert["first_seen"] = _now()
                alert["last_seen"] = _now()
                merged.append(alert)
            self._write(merged)
            return merged


def evaluate(graph: Dict, thresholds: Optional[Dict] = None) -> List[Dict]:
    """Runs every rule against a graph_data.json payload."""
    t = {
        "expected_annual_loss": 5_000_000_000.0,
        "risk_score": 70.0,
        "compliance_pct": 60.0,
        "critical_vulnerabilities": 1000,
        "overdue_actions": 500,
        **(thresholds or {}),
    }
    summary = graph.get("executive_summary") or {}
    out: List[Dict] = []

    def add(rule, severity, title, detail, value, subject=""):
        out.append({
            "id": _alert_id(rule, subject),
            "rule": rule,
            "severity": severity,
            "title": title,
            "detail": detail,
            "value": value,
            "acknowledged": False,
        })

    def _f(*keys):
        for k in keys:
            v = summary.get(k)
            if isinstance(v, (int, float)):
                return float(v)
        return None

    eal = _f("total_expected_loss", "expected_annual_loss")
    if eal is not None and eal > t["expected_annual_loss"]:
        add("eal_threshold", "Critical",
            "Expected annual loss above threshold",
            f"Rs {eal:,.0f} exceeds the Rs {t['expected_annual_loss']:,.0f} board threshold.",
            round(eal, 2))

    score = _f("enterprise_risk_score", "overall_risk_score")
    if score is not None and score > t["risk_score"]:
        add("risk_score", "High",
            "Enterprise risk score elevated",
            f"Score {score:.1f}/100 is above the {t['risk_score']:.0f} threshold.",
            round(score, 2))

    # Compliance is not in the executive summary; derive the overall posture as
    # the requirement-weighted mean of the per-framework heatmap.
    heatmap = [f for f in (graph.get("compliance_heatmap") or []) if isinstance(f, dict)]
    total_reqs = sum(f.get("total_requirements", 0) or 0 for f in heatmap)
    compliance = (
        sum((f.get("compliant", 0) or 0) * (f.get("total_requirements", 0) or 0)
            for f in heatmap) / total_reqs
        if total_reqs else None
    )
    if compliance is not None and compliance < t["compliance_pct"]:
        add("compliance_gap", "High",
            "Compliance below target",
            f"Overall posture {compliance:.1f}% is under the {t['compliance_pct']:.0f}% target.",
            round(compliance, 2))

    # severity_counts is a list of {severity, count}, not a mapping.
    counts = graph.get("severity_counts") or []
    critical = next(
        (c.get("count") for c in counts
         if isinstance(c, dict) and str(c.get("severity")).lower() == "critical"),
        None,
    )
    if isinstance(critical, (int, float)) and critical > t["critical_vulnerabilities"]:
        add("critical_vulns", "Critical",
            f"{int(critical):,} critical vulnerabilities open",
            f"Above the {t['critical_vulnerabilities']:,} threshold for critical findings.",
            int(critical))

    remediation = (graph.get("remediation") or {}).get("backlog") or {}
    overdue = remediation.get("overdue_actions")
    if isinstance(overdue, (int, float)) and overdue > t["overdue_actions"]:
        add("overdue_remediation", "High",
            f"{int(overdue):,} remediation actions overdue",
            "Past their SLA target date.",
            int(overdue))

    # Endpoint agents that stopped reporting: a silent agent is indistinguishable
    # from a compromised host, so it is worth surfacing.
    # graph_data only carries a device count; staleness lives in the registry, so
    # the alert is raised by the API layer where that store is available.

    return out


def notify_webhook(alerts: List[Dict], url: Optional[str] = None) -> bool:
    """
    Posts unacknowledged alerts to a Slack-compatible webhook.

    Opt-in: with RISKFORGE_WEBHOOK_URL unset this makes no outbound call at all.
    """
    url = url or os.environ.get("RISKFORGE_WEBHOOK_URL", "")
    fresh = [a for a in alerts if not a.get("acknowledged")]
    if not url or not fresh:
        return False

    lines = [f"*RiskForge* — {len(fresh)} active alert(s)"]
    lines += [f"• [{a['severity']}] {a['title']} — {a['detail']}" for a in fresh[:10]]
    body = json.dumps({"text": "\n".join(lines)}).encode()
    request = urllib.request.Request(
        url, data=body, headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return 200 <= response.status < 300
    except (urllib.error.URLError, OSError, ValueError):
        # Delivery is best-effort; a dead webhook must never fail a pipeline run.
        return False
