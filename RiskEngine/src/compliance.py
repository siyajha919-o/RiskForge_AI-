"""
Compliance framework mapping and evidence-based reporting.

Two things this module deliberately does NOT do:

1. It never fabricates compliance status. The previous implementation fell back
   to `np.random.choice(['Compliant','Partial','Non-Compliant'], p=[.6,.2,.2])`
   when the mapping data was missing, which silently turns a regulatory
   heatmap into random numbers. Here, missing or malformed data raises
   ComplianceDataError instead.
2. It does not assume the CSV uses the display labels. The source data uses
   "Partially Compliant" and full framework names ("ISO/IEC 27001"); those are
   normalized once, here, rather than being string-matched at each call site.
"""

from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd


class ComplianceDataError(Exception):
    """Raised when compliance data is absent or unusable. Never silently substituted."""


# Canonical short labels for the frameworks named in the problem statement.
FRAMEWORK_LABELS = {
    "ISO/IEC 27001": "ISO 27001",
    "NIST Cybersecurity Framework": "NIST CSF",
    "CIS Controls": "CIS Controls",
    "RBI Cyber Security Framework": "RBI CSF",
    "SEBI Cybersecurity and Cyber Resilience Framework": "SEBI CSCRF",
}

STATUS_LABELS = {
    "Compliant": "Compliant",
    "Partially Compliant": "Partial",
    "Partial": "Partial",
    "Non-Compliant": "Non-Compliant",
    "Noncompliant": "Non-Compliant",
}

STATUS_ORDER = ["Compliant", "Partial", "Non-Compliant"]

REQUIRED_COLUMNS = {"framework", "compliance_status", "control_id"}


class ComplianceMapper:
    def __init__(self, compliance_data: pd.DataFrame):
        if compliance_data is None or compliance_data.empty:
            raise ComplianceDataError(
                "Compliance mapping data is empty. Expected data/compliance_mapping.csv "
                "with framework/compliance_status/control_id columns. Refusing to "
                "generate a compliance report from substituted values."
            )

        missing = REQUIRED_COLUMNS - set(compliance_data.columns)
        if missing:
            raise ComplianceDataError(
                f"Compliance mapping is missing required column(s): {sorted(missing)}. "
                f"Found: {sorted(compliance_data.columns)}"
            )

        self.raw = compliance_data.copy()
        self.data = self._normalize(self.raw)

    @classmethod
    def from_csv(cls, path: Path) -> "ComplianceMapper":
        path = Path(path)
        if not path.exists():
            raise ComplianceDataError(
                f"Compliance mapping file not found: {path}. This file is required for "
                f"framework reporting (ISO 27001 / NIST CSF / CIS / RBI CSF / SEBI CSCRF)."
            )
        return cls(pd.read_csv(path))

    def _normalize(self, df: pd.DataFrame) -> pd.DataFrame:
        out = df.copy()
        out["framework_label"] = out["framework"].map(FRAMEWORK_LABELS).fillna(out["framework"])
        out["status_label"] = out["compliance_status"].map(STATUS_LABELS)

        unmapped = out["status_label"].isna()
        if unmapped.any():
            unknown = sorted(out.loc[unmapped, "compliance_status"].dropna().unique())
            raise ComplianceDataError(
                f"Unrecognized compliance_status value(s): {unknown}. "
                f"Expected one of {sorted(set(STATUS_LABELS))}. Add a mapping to "
                f"STATUS_LABELS rather than letting these be dropped from the report."
            )

        if "gap_score" in out.columns:
            out["gap_score"] = pd.to_numeric(out["gap_score"], errors="coerce")
        if "evidence_available" in out.columns:
            out["evidence_available"] = (
                out["evidence_available"].astype(str).str.strip().str.lower().isin(["true", "1", "yes"])
            )
        return out

    def framework_summary(self) -> pd.DataFrame:
        """Per-framework compliance percentages that actually sum to 100."""
        pivot = pd.crosstab(self.data["framework_label"], self.data["status_label"])
        for status in STATUS_ORDER:
            if status not in pivot.columns:
                pivot[status] = 0
        pivot = pivot[STATUS_ORDER]

        pct = pivot.div(pivot.sum(axis=1), axis=0) * 100
        pct = pct.reset_index()
        pct["total_requirements"] = pivot.sum(axis=1).values

        if "gap_score" in self.data.columns:
            gaps = self.data.groupby("framework_label")["gap_score"].mean().reset_index()
            gaps.columns = ["framework_label", "avg_gap_score"]
            pct = pct.merge(gaps, on="framework_label", how="left")

        if "evidence_available" in self.data.columns:
            ev = self.data.groupby("framework_label")["evidence_available"].mean().reset_index()
            ev.columns = ["framework_label", "evidence_coverage_pct"]
            ev["evidence_coverage_pct"] *= 100
            pct = pct.merge(ev, on="framework_label", how="left")

        return pct

    def heatmap_data(self) -> List[Dict]:
        """Chart-ready compliance heatmap. Percentages sum to 100 per framework."""
        summary = self.framework_summary()
        rows = []
        for _, row in summary.iterrows():
            rows.append(
                {
                    "framework": str(row["framework_label"]),
                    "compliant": round(float(row["Compliant"]), 1),
                    "partial": round(float(row["Partial"]), 1),
                    "non_compliant": round(float(row["Non-Compliant"]), 1),
                    "total_requirements": int(row["total_requirements"]),
                    "avg_gap_score": (
                        round(float(row["avg_gap_score"]), 3)
                        if "avg_gap_score" in row and pd.notna(row["avg_gap_score"])
                        else None
                    ),
                    "evidence_coverage_pct": (
                        round(float(row["evidence_coverage_pct"]), 1)
                        if "evidence_coverage_pct" in row and pd.notna(row["evidence_coverage_pct"])
                        else None
                    ),
                }
            )
        return rows

    def gaps(self, framework: Optional[str] = None, limit: int = 50) -> List[Dict]:
        """Non-compliant / partial requirements, worst gap score first."""
        df = self.data[self.data["status_label"] != "Compliant"]
        if framework:
            df = df[df["framework_label"] == framework]
        if "gap_score" in df.columns:
            df = df.sort_values("gap_score", ascending=False)

        cols = [
            c
            for c in [
                "framework_label",
                "requirement_id",
                "framework_function",
                "framework_category",
                "control_id",
                "status_label",
                "gap_score",
                "evidence_available",
                "evidence_quality",
            ]
            if c in df.columns
        ]
        return df[cols].head(limit).to_dict(orient="records")


class ComplianceReportGenerator:
    """
    Produces the evidence pack an auditor or regulator asks for: per framework,
    which requirements are met, which control satisfies each, whether evidence
    exists, and how strong that evidence is.
    """

    def __init__(self, mapper: ComplianceMapper, controls: Optional[pd.DataFrame] = None):
        self.mapper = mapper
        self.controls = controls if controls is not None else pd.DataFrame()

    def _control_lookup(self) -> Dict[str, Dict]:
        if self.controls.empty or "control_id" not in self.controls.columns:
            return {}
        cols = [
            c
            for c in ["control_id", "control_name", "control_category", "implementation_status", "effectiveness_score"]
            if c in self.controls.columns
        ]
        return {
            str(r["control_id"]): {k: r[k] for k in cols if k != "control_id"}
            for _, r in self.controls[cols].drop_duplicates(subset="control_id").iterrows()
        }

    def build(self) -> Dict:
        lookup = self._control_lookup()
        data = self.mapper.data
        report: Dict = {
            "generated_at": datetime.now().isoformat(),
            "frameworks": {},
            "summary": {
                "total_requirements": int(len(data)),
                "frameworks_assessed": int(data["framework_label"].nunique()),
            },
        }

        for framework, group in data.groupby("framework_label"):
            requirements = []
            for _, row in group.iterrows():
                control_id = str(row.get("control_id", ""))
                control = lookup.get(control_id, {})
                requirements.append(
                    {
                        "requirement_id": str(row.get("requirement_id", "")),
                        "function": str(row.get("framework_function", "")),
                        "category": str(row.get("framework_category", "")),
                        "status": row["status_label"],
                        "control_id": control_id,
                        "control_name": str(control.get("control_name", "")),
                        "control_implementation_status": str(control.get("implementation_status", "")),
                        "control_effectiveness": (
                            round(float(control["effectiveness_score"]), 3)
                            if control.get("effectiveness_score") is not None
                            and pd.notna(control.get("effectiveness_score"))
                            else None
                        ),
                        "evidence_available": bool(row.get("evidence_available", False)),
                        "evidence_quality": str(row.get("evidence_quality", "None")),
                        "gap_score": (
                            round(float(row["gap_score"]), 3)
                            if "gap_score" in row and pd.notna(row["gap_score"])
                            else None
                        ),
                    }
                )

            counts = group["status_label"].value_counts()
            total = int(len(group))
            evidence_backed = int(group.get("evidence_available", pd.Series(dtype=bool)).sum()) if "evidence_available" in group else 0

            report["frameworks"][framework] = {
                "total_requirements": total,
                "compliant": int(counts.get("Compliant", 0)),
                "partial": int(counts.get("Partial", 0)),
                "non_compliant": int(counts.get("Non-Compliant", 0)),
                "compliance_pct": round(int(counts.get("Compliant", 0)) / total * 100, 1) if total else 0.0,
                "evidence_backed_requirements": evidence_backed,
                "evidence_coverage_pct": round(evidence_backed / total * 100, 1) if total else 0.0,
                "requirements": requirements,
            }

        return report

    def to_markdown(self, report: Optional[Dict] = None) -> str:
        """Human-readable version for audit committees and board packs."""
        report = report or self.build()
        lines = [
            "# Cyber Security Compliance Evidence Report",
            "",
            f"Generated: {report['generated_at']}",
            f"Frameworks assessed: {report['summary']['frameworks_assessed']}  ",
            f"Total requirements: {report['summary']['total_requirements']}",
            "",
            "## Summary by framework",
            "",
            "| Framework | Requirements | Compliant | Partial | Non-Compliant | Compliance % | Evidence coverage % |",
            "|---|---|---|---|---|---|---|",
        ]

        for name, fw in report["frameworks"].items():
            lines.append(
                f"| {name} | {fw['total_requirements']} | {fw['compliant']} | {fw['partial']} | "
                f"{fw['non_compliant']} | {fw['compliance_pct']}% | {fw['evidence_coverage_pct']}% |"
            )

        for name, fw in report["frameworks"].items():
            lines += ["", f"## {name}", ""]

            unevidenced = [
                r for r in fw["requirements"] if r["status"] == "Compliant" and not r["evidence_available"]
            ]
            if unevidenced:
                lines += [
                    f"**{len(unevidenced)} requirement(s) marked Compliant have no supporting evidence.** "
                    "These are the first thing an auditor will challenge.",
                    "",
                ]

            open_items = [r for r in fw["requirements"] if r["status"] != "Compliant"]
            if open_items:
                open_items = sorted(open_items, key=lambda r: r["gap_score"] or 0, reverse=True)
                lines += [
                    "### Open findings (highest gap first)",
                    "",
                    "| Requirement | Category | Status | Control | Evidence | Gap |",
                    "|---|---|---|---|---|---|",
                ]
                for r in open_items[:25]:
                    evidence = r["evidence_quality"] if r["evidence_available"] else "None"
                    control = r["control_name"] or r["control_id"] or "—"
                    lines.append(
                        f"| {r['requirement_id']} | {r['category']} | {r['status']} | "
                        f"{control} | {evidence} | {r['gap_score'] if r['gap_score'] is not None else '—'} |"
                    )
                lines.append("")

        return "\n".join(lines)

    def export(self, json_path: Path, markdown_path: Path) -> Dict:
        import json

        report = self.build()
        json_path = Path(json_path)
        markdown_path = Path(markdown_path)
        json_path.parent.mkdir(parents=True, exist_ok=True)

        with open(json_path, "w") as f:
            json.dump(report, f, indent=2)
        with open(markdown_path, "w") as f:
            f.write(self.to_markdown(report))

        return report
