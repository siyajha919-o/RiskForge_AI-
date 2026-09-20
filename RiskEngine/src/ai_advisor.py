"""
Natural-language interface and mitigation narratives.

Design rule: every number comes from the engine. A question is answered by
retrieving the already-computed FAIR/optimization/compliance slices it refers to
and rendering them directly — nothing estimates, infers, or does arithmetic on
the way to a figure. That keeps the financial numbers auditable, which matters
more here than fluency.

Answers are produced deterministically, so the same question against the same
pipeline output always returns the same figures, and the endpoint has no
external dependency or API key to configure.
"""

import json
from pathlib import Path
from typing import Dict, Optional


class AIAdvisor:
    def __init__(self, output_dir: Path, api_key: Optional[str] = None):
        # api_key is accepted and ignored so existing callers keep working.
        self.output_dir = Path(output_dir)

    # ------------------------------------------------------------------
    # Retrieval — pull only the slices a question actually needs, so the
    # answer stays focused instead of dumping every computed figure.
    # ------------------------------------------------------------------

    def _load(self, filename: str) -> Dict:
        path = self.output_dir / filename
        if not path.exists():
            return {}
        try:
            with open(path) as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {}

    def _retrieve(self, question: str) -> Dict:
        graph = self._load("graph_data.json")
        q = question.lower()
        context: Dict = {"executive_summary": graph.get("executive_summary", {})}

        def wants(*words):
            return any(w in q for w in words)

        if wants("top", "highest", "worst", "biggest", "contributor", "driver"):
            context["top_assets_by_risk"] = graph.get("asset_risk_scores", [])
            context["business_units"] = graph.get("business_unit_risk", {}).get("by_business_unit", [])[:10]

        if wants("vulnerabilit", "cve", "patch", "cvss"):
            context["vulnerability_severity_counts"] = graph.get("severity_counts", [])

        if wants("business unit", "department", "division", "bu ", "unit"):
            context["business_units"] = graph.get("business_unit_risk", {}).get("by_business_unit", [])

        if wants("organisation", "organization", "company", "enterprise", "overall"):
            context["organizations"] = graph.get("business_unit_risk", {}).get("by_organization", [])

        if wants("compliance", "iso", "nist", "sebi", "rbi", "cis", "regulat", "audit"):
            context["compliance"] = graph.get("compliance_heatmap", [])
            report = self._load("compliance_report.json")
            if report:
                context["compliance_summary"] = {
                    name: {k: v for k, v in fw.items() if k != "requirements"}
                    for name, fw in report.get("frameworks", {}).items()
                }

        if wants("invest", "budget", "spend", "rosi", "roi", "control", "mitigat", "fix", "remediat"):
            context["investment_frontier"] = graph.get("efficient_frontier", [])
            context["selected_controls"] = graph.get("rosi_per_control", [])
            context["control_effectiveness"] = graph.get("control_effectiveness", [])

        if wants("scenario", "what if", "what-if", "simulate", "mfa", "delay", "segment"):
            context["what_if_scenarios"] = graph.get("what_if_scenarios", [])

        if wants("attack", "path", "lateral", "exploit chain", "kill chain"):
            context["attack_paths"] = graph.get("attack_paths", {})

        if wants("var", "value at risk", "worst case", "tail"):
            context["var_curve_tail"] = graph.get("var_curve", [])[:10]

        # Nothing matched a specific topic — give the headline numbers only.
        if len(context) == 1:
            context["business_units"] = graph.get("business_unit_risk", {}).get("by_business_unit", [])[:5]
            context["top_assets_by_risk"] = graph.get("asset_risk_scores", [])[:5]

        return context

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def answer(self, question: str) -> Dict:
        context = self._retrieve(question)
        return {
            "question": question,
            "answer": self._render(context),
            "mode": "deterministic",
            "context_used": sorted(context),
        }

    def explain_recommendations(self, top_n: int = 5) -> Dict:
        """Return the optimizer's control selection, highest ROSI first."""
        graph = self._load("graph_data.json")
        return {
            "recommendations": graph.get("rosi_per_control", [])[:top_n],
            "mode": "deterministic",
        }

    def _render(self, context: Dict) -> str:
        """Render the retrieved figures as plain text."""
        lines = []
        summary = context.get("executive_summary", {})
        if summary.get("total_expected_loss"):
            lines.append(f"Total expected annual loss: ₹{summary['total_expected_loss']:,.0f}")
        if summary.get("var_95"):
            lines.append(f"Value at Risk (95%): ₹{summary['var_95']:,.0f}")

        for bu in context.get("business_units", [])[:5]:
            lines.append(
                f"  {bu.get('business_unit_name', bu.get('business_unit_id'))}: "
                f"₹{bu.get('expected_annual_loss', 0):,.0f}"
            )
        for asset in context.get("top_assets_by_risk", [])[:5]:
            lines.append(f"  {asset.get('asset_id')}: risk score {asset.get('risk_score')}")
        for scenario in context.get("what_if_scenarios", []):
            lines.append(
                f"  {scenario.get('scenario')}: {scenario.get('percent_change'):+.1f}% "
                f"({scenario.get('direction')})"
            )

        return "\n".join(lines) if lines else "No computed risk data available yet. Run the pipeline first."
