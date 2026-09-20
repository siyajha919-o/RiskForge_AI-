"""
Per-run risk snapshots — the time series behind "Risk Trend Analysis".

The engine recomputes risk continuously but previously kept only the latest
figures, so there was nothing to plot a trend from and no way to answer whether
exposure is improving. Each successful run appends one snapshot here.

Snapshots are append-only and keyed by run timestamp. Same-day reruns replace
that day's point rather than stacking, so the chart stays one-point-per-day
regardless of how often the scheduler fires.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


class RiskHistory:
    def __init__(self, path: Path, max_points: int = 365):
        self.path = Path(path)
        self.max_points = max_points

    def _load(self) -> List[Dict]:
        if not self.path.exists():
            return []
        try:
            with open(self.path) as f:
                data = json.load(f)
            return data if isinstance(data, list) else []
        except (json.JSONDecodeError, OSError):
            return []

    def append(
        self,
        expected_annual_loss: float,
        var_95: float,
        var_99: float = 0.0,
        assets_simulated: int = 0,
        open_vulnerabilities: int = 0,
        avg_control_effectiveness: float = 0.0,
        compliance_pct: float = 0.0,
        annual_revenue: float = 0.0,
        run_mode: str = "full",
    ) -> Dict:
        now = datetime.now()
        snapshot = {
            "timestamp": now.isoformat(),
            "date": now.strftime("%Y-%m-%d"),
            "expected_annual_loss": round(float(expected_annual_loss), 2),
            "var_95": round(float(var_95), 2),
            "var_99": round(float(var_99), 2),
            "assets_simulated": int(assets_simulated),
            "open_vulnerabilities": int(open_vulnerabilities),
            "avg_control_effectiveness": round(float(avg_control_effectiveness), 4),
            "compliance_pct": round(float(compliance_pct), 2),
            "annual_revenue": round(float(annual_revenue), 2),
            "enterprise_risk_score": self._risk_score(
                expected_annual_loss, avg_control_effectiveness, compliance_pct, annual_revenue
            ),
            "run_mode": run_mode,
        }

        history = [h for h in self._load() if h.get("date") != snapshot["date"]]
        history.append(snapshot)
        history.sort(key=lambda h: h.get("timestamp", ""))
        history = history[-self.max_points:]

        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "w") as f:
            json.dump(history, f, indent=2)

        return snapshot

    @staticmethod
    def _risk_score(expected_annual_loss: float, control_effectiveness: float,
                    compliance_pct: float, annual_revenue: float = 0.0) -> float:
        """
        Enterprise Risk Score, 0-100 (higher = riskier).

        The single headline number the board tracks between meetings, and the
        one the trend chart plots — so it is computed here once and persisted,
        never recomputed differently by the API layer.

        Exposure is anchored to revenue when known (20%+ of revenue at risk is a
        full-scale reading), because ₹80 crore means something different to a
        ₹200 crore business than a ₹20,000 crore one. Without revenue it falls
        back to a log scale, since losses span orders of magnitude and a linear
        one would peg the needle permanently.
        """
        import math

        if expected_annual_loss <= 0:
            exposure_component = 0.0
        elif annual_revenue > 0:
            exposure_component = min(100.0, (expected_annual_loss / annual_revenue) / 0.20 * 100)
        else:
            # ~₹1 lakh -> 0, ~₹1000 crore -> 100
            exposure_component = min(
                100.0, max(0.0, (math.log10(expected_annual_loss) - 5) / 5 * 100)
            )

        control_component = (1 - min(max(control_effectiveness, 0.0), 1.0)) * 100
        compliance_component = 100 - min(max(compliance_pct, 0.0), 100.0)

        score = 0.5 * exposure_component + 0.3 * control_component + 0.2 * compliance_component
        return round(min(100.0, max(0.0, score)), 1)

    def series(self, limit: Optional[int] = None) -> List[Dict]:
        history = self._load()
        return history[-limit:] if limit else history

    def trend_data(self, limit: int = 30) -> Dict:
        """Chart-ready trend series for the dashboard."""
        history = self.series(limit)

        risk_trend = [
            {
                "date": h["date"],
                "risk_score": h.get("enterprise_risk_score", 0),
                "control_effectiveness": round(h.get("avg_control_effectiveness", 0) * 100, 1),
                "compliance_pct": h.get("compliance_pct", 0),
            }
            for h in history
        ]

        financial_exposure_trend = [
            {
                "date": h["date"],
                "expected_annual_loss": h.get("expected_annual_loss", 0),
                "var_95": h.get("var_95", 0),
            }
            for h in history
        ]

        direction = "flat"
        change_pct = 0.0
        if len(history) >= 2:
            first = history[0].get("expected_annual_loss", 0)
            last = history[-1].get("expected_annual_loss", 0)
            if first:
                change_pct = round((last - first) / first * 100, 2)
                direction = "improving" if change_pct < -1 else ("worsening" if change_pct > 1 else "flat")

        return {
            "risk_trend": risk_trend,
            "financial_exposure_trend": financial_exposure_trend,
            "points": len(history),
            "direction": direction,
            "change_pct": change_pct,
            "current_risk_score": history[-1].get("enterprise_risk_score") if history else None,
        }
