from fastapi import APIRouter, Depends

from .. import services as svc
from ..models import (
    DashboardResponse, RiskCards, RiskContributor, RiskDistribution, TopRisk, UserOut,
)
from ..security import current_user

router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])


@router.get("", response_model=DashboardResponse)
def dashboard(user: UserOut = Depends(current_user)):
    graph = svc.graph_data()
    summary = svc.executive_summary()
    score = svc.overall_risk_score()

    cards = RiskCards(
        overall_risk_score=score,
        risk_level=svc.risk_level_from_score(score),
        expected_annual_loss=summary.get("total_expected_loss", 0) or 0,
        total_financial_exposure=summary.get("var_95", 0) or 0,
        critical_vulnerabilities=svc.critical_vulnerability_count(),
        active_high_risk_threats=svc.active_high_risk_threats(),
    )

    dist = svc.severity_distribution()

    # Contributors come from the business-unit rollup when the pipeline has
    # produced one; otherwise from per-asset scores, which are always present.
    contributors = []
    units = graph.get("business_unit_risk", {}).get("by_business_unit", [])
    total_eal = sum(u.get("expected_annual_loss", 0) for u in units) or 1

    for u in sorted(units, key=lambda x: -x.get("expected_annual_loss", 0))[:8]:
        eal = u.get("expected_annual_loss", 0)
        share = eal / total_eal * 100
        contributors.append(RiskContributor(
            name=u.get("business_unit_name") or u.get("business_unit_id", "Unknown"),
            category=u.get("business_function") or "Business unit",
            expected_annual_loss=eal,
            contribution_pct=round(share, 2),
            risk_level=svc.risk_level_from_score(min(100, share * 4)),
        ))

    if not contributors:
        assets = graph.get("asset_risk_scores", [])
        total = sum(a.get("risk_score", 0) for a in assets) or 1
        for a in assets[:8]:
            share = a.get("risk_score", 0) / total * 100
            contributors.append(RiskContributor(
                name=a.get("asset_id", "Unknown"),
                category="Asset",
                expected_annual_loss=0,
                contribution_pct=round(share, 2),
                risk_level=svc.risk_level_from_score(a.get("risk_score", 0) * 100),
            ))

    top_risks = []
    for i, u in enumerate(sorted(units, key=lambda x: -x.get("expected_annual_loss", 0))[:5], 1):
        top_risks.append(TopRisk(
            rank=i,
            title=f"Concentrated exposure in {u.get('business_unit_name') or u.get('business_unit_id')}",
            business_unit=u.get("business_unit_name"),
            expected_annual_loss=u.get("expected_annual_loss", 0),
            risk_level=svc.risk_level_from_score(min(100, u.get("loss_as_pct_of_revenue", 0) * 20)),
            driver=f"{u.get('asset_count', 0)} assets, "
                   f"{u.get('total_vulnerabilities', 0)} open vulnerabilities",
        ))

    if not top_risks:
        for i, a in enumerate(graph.get("asset_risk_scores", [])[:5], 1):
            top_risks.append(TopRisk(
                rank=i,
                title=f"High residual risk on {a.get('asset_id')}",
                asset_id=a.get("asset_id"),
                expected_annual_loss=0,
                risk_level=svc.risk_level_from_score(a.get("risk_score", 0) * 100),
                driver="Residual risk after existing controls",
            ))

    meta = graph.get("metadata", {})
    return DashboardResponse(
        cards=cards,
        risk_trend=svc.risk_trend(),
        financial_exposure_trend=svc.exposure_trend(),
        risk_distribution=RiskDistribution(**dist),
        top_contributors=contributors,
        top_risks=top_risks,
        generated_at=meta.get("generated_at"),
        run_mode=meta.get("run_mode"),
        trend_is_measured=svc.trend_is_measured(),
    )
