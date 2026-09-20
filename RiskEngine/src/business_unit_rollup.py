"""
Rolls per-asset FAIR results up to business-unit and organization level.

The problem statement asks for financial exposure "at organization, business
unit, and asset levels". The FAIR simulation produces asset-level ALE/VaR;
this module attaches each asset to its business unit and organization and
aggregates, so exposure can be reported in the terms a CISO or board actually
uses (per business function, against that unit's revenue contribution).
"""

from typing import Dict, List

import numpy as np
import pandas as pd


class BusinessUnitRollup:
    def __init__(
        self,
        fair_results: pd.DataFrame,
        assets: pd.DataFrame,
        business_units: pd.DataFrame,
        organizations: pd.DataFrame,
    ):
        self.fair_results = fair_results if fair_results is not None else pd.DataFrame()
        self.assets = assets if assets is not None else pd.DataFrame()
        self.business_units = business_units if business_units is not None else pd.DataFrame()
        self.organizations = organizations if organizations is not None else pd.DataFrame()
        self.enriched = pd.DataFrame()

    def _enrich(self) -> pd.DataFrame:
        """Attach business_unit_id / organization_id to each simulated asset."""
        if self.fair_results.empty or self.assets.empty:
            return pd.DataFrame()

        if "asset_id" not in self.fair_results.columns or "asset_id" not in self.assets.columns:
            return pd.DataFrame()

        asset_cols = [
            c
            for c in ["asset_id", "business_unit_id", "organization_id", "asset_name", "business_service"]
            if c in self.assets.columns
        ]

        merged = self.fair_results.merge(
            self.assets[asset_cols].drop_duplicates(subset="asset_id"),
            on="asset_id",
            how="left",
        )

        if "business_unit_id" in merged.columns:
            merged["business_unit_id"] = merged["business_unit_id"].fillna("UNASSIGNED")
        if "organization_id" in merged.columns:
            merged["organization_id"] = merged["organization_id"].fillna("UNASSIGNED")

        self.enriched = merged
        return merged

    def by_business_unit(self) -> pd.DataFrame:
        """Aggregate exposure per business unit, with BU context joined in."""
        enriched = self.enriched if not self.enriched.empty else self._enrich()
        if enriched.empty or "business_unit_id" not in enriched.columns:
            return pd.DataFrame()

        agg = (
            enriched.groupby("business_unit_id")
            .agg(
                asset_count=("asset_id", "count"),
                expected_annual_loss=("expected_ale", "sum"),
                avg_ale_per_asset=("expected_ale", "mean"),
                max_asset_ale=("expected_ale", "max"),
                var_95=("var_95", "sum"),
                avg_control_effectiveness=("control_effectiveness", "mean"),
                total_vulnerabilities=("vuln_count", "sum"),
            )
            .reset_index()
        )

        if not self.business_units.empty and "business_unit_id" in self.business_units.columns:
            bu_cols = [
                c
                for c in [
                    "business_unit_id",
                    "organization_id",
                    "business_unit_name",
                    "business_function",
                    "annual_revenue_contribution",
                    "criticality_score",
                    "regulatory_importance",
                    "maximum_tolerable_downtime_hours",
                ]
                if c in self.business_units.columns
            ]
            agg = agg.merge(self.business_units[bu_cols], on="business_unit_id", how="left")

        # Exposure as a share of the revenue the unit contributes — the number
        # that makes "is this spend proportionate?" answerable.
        if "annual_revenue_contribution" in agg.columns:
            revenue = pd.to_numeric(agg["annual_revenue_contribution"], errors="coerce")
            agg["loss_as_pct_of_revenue"] = np.where(
                revenue > 0, (agg["expected_annual_loss"] / revenue) * 100, np.nan
            )

        return agg.sort_values("expected_annual_loss", ascending=False).reset_index(drop=True)

    def by_organization(self) -> pd.DataFrame:
        enriched = self.enriched if not self.enriched.empty else self._enrich()
        if enriched.empty or "organization_id" not in enriched.columns:
            return pd.DataFrame()

        agg = (
            enriched.groupby("organization_id")
            .agg(
                asset_count=("asset_id", "count"),
                expected_annual_loss=("expected_ale", "sum"),
                var_95=("var_95", "sum"),
                avg_control_effectiveness=("control_effectiveness", "mean"),
            )
            .reset_index()
        )

        if not self.organizations.empty and "organization_id" in self.organizations.columns:
            org_cols = [
                c
                for c in [
                    "organization_id",
                    "organization_name",
                    "industry",
                    "annual_revenue",
                    "security_budget",
                    "regulatory_category",
                    "cyber_maturity_score",
                ]
                if c in self.organizations.columns
            ]
            agg = agg.merge(self.organizations[org_cols], on="organization_id", how="left")

        if "security_budget" in agg.columns:
            budget = pd.to_numeric(agg["security_budget"], errors="coerce")
            agg["exposure_to_budget_ratio"] = np.where(
                budget > 0, agg["expected_annual_loss"] / budget, np.nan
            )

        return agg.sort_values("expected_annual_loss", ascending=False).reset_index(drop=True)

    def top_assets_per_business_unit(self, top_n: int = 3) -> Dict[str, List[Dict]]:
        """Drill-down: the biggest ALE contributors inside each business unit."""
        enriched = self.enriched if not self.enriched.empty else self._enrich()
        if enriched.empty or "business_unit_id" not in enriched.columns:
            return {}

        out: Dict[str, List[Dict]] = {}
        for bu_id, group in enriched.groupby("business_unit_id"):
            top = group.nlargest(top_n, "expected_ale")
            out[str(bu_id)] = [
                {
                    "asset_id": str(row["asset_id"]),
                    "asset_name": str(row.get("asset_name", "")),
                    "expected_annual_loss": round(float(row["expected_ale"]), 2),
                    "var_95": round(float(row.get("var_95", 0)), 2),
                }
                for _, row in top.iterrows()
            ]
        return out

    def export_graph_data(self, top_n: int = 15) -> Dict:
        """Chart-ready payload for the dashboard's business-unit views."""
        bu = self.by_business_unit()
        org = self.by_organization()

        bu_chart = []
        if not bu.empty:
            for _, row in bu.head(top_n).iterrows():
                bu_chart.append(
                    {
                        "business_unit_id": str(row["business_unit_id"]),
                        "business_unit_name": str(row.get("business_unit_name", row["business_unit_id"])),
                        "business_function": str(row.get("business_function", "")),
                        "asset_count": int(row["asset_count"]),
                        "expected_annual_loss": round(float(row["expected_annual_loss"]), 2),
                        "var_95": round(float(row["var_95"]), 2),
                        "loss_as_pct_of_revenue": (
                            round(float(row["loss_as_pct_of_revenue"]), 4)
                            if "loss_as_pct_of_revenue" in row and pd.notna(row["loss_as_pct_of_revenue"])
                            else None
                        ),
                        "criticality_score": (
                            float(row["criticality_score"])
                            if "criticality_score" in row and pd.notna(row["criticality_score"])
                            else None
                        ),
                        "regulatory_importance": str(row.get("regulatory_importance", "")),
                    }
                )

        org_chart = []
        if not org.empty:
            for _, row in org.iterrows():
                org_chart.append(
                    {
                        "organization_id": str(row["organization_id"]),
                        "organization_name": str(row.get("organization_name", row["organization_id"])),
                        "asset_count": int(row["asset_count"]),
                        "expected_annual_loss": round(float(row["expected_annual_loss"]), 2),
                        "var_95": round(float(row["var_95"]), 2),
                        "exposure_to_budget_ratio": (
                            round(float(row["exposure_to_budget_ratio"]), 4)
                            if "exposure_to_budget_ratio" in row and pd.notna(row["exposure_to_budget_ratio"])
                            else None
                        ),
                    }
                )

        return {
            "by_business_unit": bu_chart,
            "by_organization": org_chart,
            "top_assets_per_business_unit": self.top_assets_per_business_unit(),
        }
