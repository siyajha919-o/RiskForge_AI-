from fastapi import APIRouter, Depends

from .. import services as svc
from ..models import RiskAnalysisResponse, RiskDriver, UserOut
from ..security import current_user

router = APIRouter(prefix="/api/v1/risk", tags=["risk"])


@router.get("/analysis", response_model=RiskAnalysisResponse)
def analysis(user: UserOut = Depends(current_user)):
    """
    Decomposes enterprise risk into the identity the screen is built around:
        incident probability x financial impact = expected annual loss
    """
    graph = svc.graph_data()
    summary = svc.executive_summary()
    eal = float(summary.get("total_expected_loss", 0) or 0)
    score = svc.overall_risk_score()

    vulns = svc.vulnerabilities()
    controls = svc.controls()

    # Annual probability of at least one material incident, from the exploitable
    # population tempered by measured control effectiveness.
    exploited = int(vulns["known_exploited"].sum()) if "known_exploited" in vulns else 0
    critical = svc.critical_vulnerability_count()
    effectiveness = (
        float(controls["effectiveness_score"].mean())
        if not controls.empty and "effectiveness_score" in controls else 0.5
    )
    raw_probability = 1 - pow(0.995, exploited + critical * 0.5)
    probability = round(min(0.99, max(0.01, raw_probability * (1 - effectiveness * 0.6))), 4)

    # Impact is the loss magnitude implied by that probability and the EAL, so
    # the three numbers on screen are mutually consistent by construction.
    impact = round(eal / probability, 2) if probability > 0 else 0.0

    # Attribute EAL across driver categories.
    weights = {
        "vulnerability": 0.0,
        "threat": 0.0,
        "asset_criticality": 0.0,
        "control_weakness": 0.0,
    }
    total_vulns = len(vulns) if not vulns.empty else 0
    if total_vulns:
        weights["vulnerability"] = min(0.45, (critical / total_vulns) * 3 + 0.15)
    weights["threat"] = min(0.30, svc.active_high_risk_threats() / 1000)
    weights["control_weakness"] = min(0.35, (1 - effectiveness) * 0.6)

    assets = svc.load_csv("assets")
    if not assets.empty and "asset_criticality" in assets:
        avg_crit = svc.numeric_criticality(assets["asset_criticality"]).mean()
        weights["asset_criticality"] = min(0.30, float(avg_crit) / 5 * 0.3)

    total_weight = sum(weights.values()) or 1
    breakdown = {k: round(v / total_weight * 100, 2) for k, v in weights.items()}

    drivers = []
    labels = {
        "vulnerability": ("Unpatched and exploitable vulnerabilities",
                          f"{critical} critical, {exploited} known-exploited"),
        "threat": ("Active threat campaigns",
                   f"{svc.active_high_risk_threats()} high-severity active campaigns"),
        "asset_criticality": ("Business-critical asset concentration",
                              "Revenue- and regulation-dependent assets"),
        "control_weakness": ("Control effectiveness gaps",
                             f"Mean control effectiveness {effectiveness:.0%}"),
    }
    for key, share in sorted(breakdown.items(), key=lambda kv: -kv[1]):
        title, detail = labels[key]
        drivers.append(RiskDriver(
            driver=title,
            category=key,
            contribution_pct=share,
            expected_annual_loss=round(eal * share / 100, 2),
            detail=detail,
        ))

    return RiskAnalysisResponse(
        overall_risk_score=score,
        risk_level=svc.risk_level_from_score(score),
        incident_probability=probability,
        estimated_financial_impact=impact,
        expected_annual_loss=eal,
        risk_trend=svc.risk_trend(),
        top_drivers=drivers,
        contribution_breakdown=breakdown,
    )


@router.get("/business-units")
def business_units(user: UserOut = Depends(current_user)):
    return svc.graph_data().get("business_unit_risk", {}).get("by_business_unit", [])


@router.get("/organizations")
def organizations(user: UserOut = Depends(current_user)):
    return svc.graph_data().get("business_unit_risk", {}).get("by_organization", [])


@router.get("/loss-curve")
def loss_curve(user: UserOut = Depends(current_user)):
    """Loss exceedance curve plus the VaR markers, for the risk analysis chart."""
    graph = svc.graph_data()
    return {
        "curve": graph.get("var_curve", []),
        "distribution": graph.get("loss_distribution", []),
        "var_95": svc.executive_summary().get("var_95", 0),
        "var_99": svc.executive_summary().get("var_99", 0),
    }
