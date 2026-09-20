from fastapi import APIRouter, Depends

from .. import services as svc
from ..models import (
    ComplianceResponse, ControlStatus, FrameworkSummary, UserOut,
)
from ..security import current_user

router = APIRouter(prefix="/api/v1/compliance", tags=["compliance"])

ACTIONS = {
    "Non-Compliant": "Implement the control and capture supporting evidence",
    "Partial": "Close the remaining gap and strengthen evidence quality",
    "Compliant": "Maintain control and refresh evidence at next review",
}


@router.get("", response_model=ComplianceResponse)
def compliance(user: UserOut = Depends(current_user), limit: int = 500):
    report = svc.compliance_report()
    frameworks_raw = report.get("frameworks", {}) if report else {}

    if not frameworks_raw:
        # Fall back to the heatmap the pipeline always emits.
        heatmap = svc.graph_data().get("compliance_heatmap", [])
        summaries = [
            FrameworkSummary(
                framework=h["framework"],
                total_requirements=h.get("total_requirements", 0),
                compliant=round(h.get("compliant", 0) / 100 * h.get("total_requirements", 0)),
                partial=round(h.get("partial", 0) / 100 * h.get("total_requirements", 0)),
                gaps=round(h.get("non_compliant", 0) / 100 * h.get("total_requirements", 0)),
                compliance_score=h.get("compliant", 0),
                evidence_coverage_pct=h.get("evidence_coverage_pct") or 0,
            )
            for h in heatmap
        ]
        total = sum(s.total_requirements for s in summaries) or 1
        return ComplianceResponse(
            overall_compliance_score=round(
                sum(s.compliance_score * s.total_requirements for s in summaries) / total, 1),
            total_compliant=sum(s.compliant for s in summaries),
            total_partial=sum(s.partial for s in summaries),
            total_gaps=sum(s.gaps for s in summaries),
            frameworks=summaries,
            controls=[],
        )

    eal = float(svc.executive_summary().get("total_expected_loss", 0) or 0)
    total_gap_score = 0.0
    for fw in frameworks_raw.values():
        for r in fw.get("requirements", []):
            total_gap_score += (r.get("gap_score") or 0)

    summaries, controls = [], []
    for name, fw in frameworks_raw.items():
        summaries.append(FrameworkSummary(
            framework=name,
            total_requirements=fw.get("total_requirements", 0),
            compliant=fw.get("compliant", 0),
            partial=fw.get("partial", 0),
            gaps=fw.get("non_compliant", 0),
            compliance_score=fw.get("compliance_pct", 0),
            evidence_coverage_pct=fw.get("evidence_coverage_pct", 0),
        ))

        for r in fw.get("requirements", []):
            gap = r.get("gap_score") or 0
            controls.append(ControlStatus(
                requirement_id=r.get("requirement_id", ""),
                framework=name,
                function=r.get("function"),
                category=r.get("category"),
                control_id=r.get("control_id", ""),
                control_name=r.get("control_name") or None,
                status=r.get("status", "Non-Compliant"),
                evidence_available=bool(r.get("evidence_available")),
                evidence_quality=r.get("evidence_quality", "None"),
                gap_score=gap,
                # Attribute enterprise EAL across open gaps by gap severity.
                associated_risk=round(eal * gap / total_gap_score, 2) if total_gap_score else None,
                recommended_action=ACTIONS.get(r.get("status", ""), None),
            ))

    total_reqs = sum(s.total_requirements for s in summaries) or 1
    return ComplianceResponse(
        overall_compliance_score=round(
            sum(s.compliance_score * s.total_requirements for s in summaries) / total_reqs, 1),
        total_compliant=sum(s.compliant for s in summaries),
        total_partial=sum(s.partial for s in summaries),
        total_gaps=sum(s.gaps for s in summaries),
        frameworks=summaries,
        # Gaps first — that is what the screen is for.
        controls=sorted(controls, key=lambda c: -(c.gap_score or 0))[:limit],
    )
