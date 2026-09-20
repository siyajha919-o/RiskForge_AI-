"""
Remediation backlog and prioritized mitigation actions.

data/remediation_actions.csv carries 30k rows that map directly onto two
requirements the platform previously left unmet: prioritized mitigation
recommendations with quantified risk reduction, and a remediation backlog for
technical drill-down. The file was being loaded and then dropped.

Prioritization here is deterministic: actions are ranked by expected loss
reduction per rupee spent, not by the qualitative Critical/High/Medium/Low
label — the whole point of the platform is to replace that ordering with a
financial one.
"""

from typing import Dict, List, Optional

import numpy as np
import pandas as pd

OPEN_STATUSES = {"Pending", "In Progress", "Overdue"}


class RemediationPlanner:
    def __init__(self, remediation: pd.DataFrame, assets: Optional[pd.DataFrame] = None):
        self.raw = remediation if remediation is not None else pd.DataFrame()
        self.assets = assets if assets is not None else pd.DataFrame()
        self.data = self._prepare(self.raw)

    def _prepare(self, df: pd.DataFrame) -> pd.DataFrame:
        if df is None or df.empty:
            return pd.DataFrame()

        out = df.copy()
        for col in ["estimated_cost", "expected_risk_reduction", "expected_loss_reduction",
                    "implementation_time_days"]:
            if col in out.columns:
                out[col] = pd.to_numeric(out[col], errors="coerce").fillna(0)

        # Loss reduction per rupee — the ranking that actually matters.
        if {"expected_loss_reduction", "estimated_cost"}.issubset(out.columns):
            out["roi_ratio"] = np.where(
                out["estimated_cost"] > 0,
                out["expected_loss_reduction"] / out["estimated_cost"],
                0.0,
            )
        else:
            out["roi_ratio"] = 0.0

        if "status" in out.columns:
            out["is_open"] = out["status"].isin(OPEN_STATUSES)
        else:
            out["is_open"] = True

        # Attach business context so a recommendation can name the affected service.
        if not self.assets.empty and "asset_id" in out.columns and "asset_id" in self.assets.columns:
            cols = [c for c in ["asset_id", "asset_name", "business_unit_id", "business_service",
                                "asset_criticality"] if c in self.assets.columns]
            out = out.merge(self.assets[cols].drop_duplicates(subset="asset_id"),
                            on="asset_id", how="left")
        return out

    def top_recommendations(self, limit: int = 20, open_only: bool = True) -> List[Dict]:
        """Prioritized actions, best financial return first."""
        if self.data.empty:
            return []

        df = self.data[self.data["is_open"]] if open_only else self.data
        df = df.sort_values("roi_ratio", ascending=False).head(limit)

        return [
            {
                "remediation_id": str(r.get("remediation_id", "")),
                "action": str(r.get("recommended_action", "")),
                "category": str(r.get("action_category", "")),
                "asset_id": str(r.get("asset_id", "")),
                "asset_name": str(r.get("asset_name", "")),
                "business_service": str(r.get("business_service", "")),
                "vulnerability_id": str(r.get("vulnerability_id", "")),
                "required_control": str(r.get("required_control", "")),
                "estimated_cost": round(float(r.get("estimated_cost", 0)), 2),
                "expected_loss_reduction": round(float(r.get("expected_loss_reduction", 0)), 2),
                "expected_risk_reduction_pct": round(float(r.get("expected_risk_reduction", 0)), 2),
                "return_per_rupee": round(float(r.get("roi_ratio", 0)), 2),
                "implementation_days": int(r.get("implementation_time_days", 0) or 0),
                "priority": str(r.get("priority", "")),
                "status": str(r.get("status", "")),
                "deadline": str(r.get("recommended_deadline", "")),
                "dependency": str(r.get("dependency", "")),
            }
            for _, r in df.iterrows()
        ]

    def backlog_summary(self) -> Dict:
        """Backlog health for the technical dashboard."""
        if self.data.empty:
            return {}

        by_status = self.data["status"].value_counts().to_dict() if "status" in self.data else {}
        by_priority = self.data["priority"].value_counts().to_dict() if "priority" in self.data else {}
        by_category = (
            self.data.groupby("action_category")
            .agg(count=("remediation_id", "count"),
                 total_cost=("estimated_cost", "sum"),
                 total_loss_reduction=("expected_loss_reduction", "sum"))
            .reset_index()
            .sort_values("total_loss_reduction", ascending=False)
        )

        open_items = self.data[self.data["is_open"]]

        return {
            "total_actions": int(len(self.data)),
            "open_actions": int(len(open_items)),
            "overdue_actions": int((self.data["status"] == "Overdue").sum()) if "status" in self.data else 0,
            "by_status": {str(k): int(v) for k, v in by_status.items()},
            "by_priority": {str(k): int(v) for k, v in by_priority.items()},
            "open_cost_to_clear": round(float(open_items["estimated_cost"].sum()), 2),
            "open_loss_reduction_available": round(float(open_items["expected_loss_reduction"].sum()), 2),
            "by_category": [
                {
                    "category": str(r["action_category"]),
                    "count": int(r["count"]),
                    "total_cost": round(float(r["total_cost"]), 2),
                    "total_loss_reduction": round(float(r["total_loss_reduction"]), 2),
                }
                for _, r in by_category.iterrows()
            ],
        }

    def export_graph_data(self, limit: int = 20) -> Dict:
        return {
            "top_recommendations": self.top_recommendations(limit=limit),
            "backlog": self.backlog_summary(),
        }
