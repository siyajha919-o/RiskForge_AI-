from fastapi import APIRouter, Depends, HTTPException

from .. import services as svc
from ..models import (
    ControlOption, Role, SimulationRequest, SimulationResponse, SimulationState, UserOut,
)
from ..security import current_user, require_roles

router = APIRouter(prefix="/api/v1/scenarios", tags=["scenarios"])

# The four controls the brief names, mapped onto the control catalogue by
# category keyword. Falls back to a modelled default when the estate has no
# matching control, so the screen always has something to simulate.
NAMED_CONTROLS = {
    "MFA": {"keywords": ["multi-factor", "mfa", "authentication", "identity"],
            "reduction": 32.0, "cost": 4_500_000,
            "description": "Multi-factor authentication on all privileged accounts"},
    "EDR": {"keywords": ["endpoint", "edr", "detection", "antivirus"],
            "reduction": 28.0, "cost": 7_200_000,
            "description": "Endpoint detection and response across managed endpoints"},
    "Critical Patching": {"keywords": ["patch", "vulnerability management", "update"],
                          "reduction": 35.0, "cost": 3_800_000,
                          "description": "Accelerated patching for critical and known-exploited CVEs"},
    "Network Segmentation": {"keywords": ["segment", "network", "firewall", "zero trust"],
                             "reduction": 24.0, "cost": 9_500_000,
                             "description": "Segment critical services to limit lateral movement"},
}


def _catalogue() -> list[ControlOption]:
    controls = svc.controls()
    out: list[ControlOption] = []

    for name, spec in NAMED_CONTROLS.items():
        hits = None
        if not controls.empty and "control_name" in controls.columns:
            haystack = (
                controls["control_name"].astype(str).str.lower()
                + " " + controls.get("control_category", "").astype(str).str.lower()
            )
            found = controls[haystack.apply(lambda h: any(k in h for k in spec["keywords"]))]
            if not found.empty:
                hits = found

        if hits is not None:
            # security_controls.csv has one row per organization that deployed
            # this control. A single row's cost (e.g. one org's ₹65k MFA
            # instance) is the cost of protecting that one org, not the whole
            # estate -- applying it against enterprise-wide EAL understated
            # cost by ~50x and produced a nonsensical ROSI. Sum cost across
            # every deployed instance; average the reduction/effectiveness,
            # since those describe the control's per-asset effect, not a
            # quantity that accumulates with more deployments.
            out.append(ControlOption(
                control_id=str(hits.iloc[0].get("control_id", name)),
                name=name,
                category=str(hits.iloc[0].get("control_category", "Security control")),
                annual_cost=float(hits["annual_cost"].sum()) if "annual_cost" in hits else spec["cost"],
                implementation_cost=(
                    float(hits["implementation_cost"].sum()) if "implementation_cost" in hits else 0.0
                ),
                expected_risk_reduction_pct=(
                    float(hits["risk_reduction_percentage"].mean())
                    if "risk_reduction_percentage" in hits else spec["reduction"]
                ),
                effectiveness_score=(
                    float(hits["effectiveness_score"].mean()) if "effectiveness_score" in hits else 0.6
                ),
                description=spec["description"],
            ))
        else:
            out.append(ControlOption(
                control_id=name.replace(" ", "_").upper(),
                name=name,
                category="Security control",
                annual_cost=spec["cost"],
                implementation_cost=spec["cost"] * 0.4,
                expected_risk_reduction_pct=spec["reduction"],
                effectiveness_score=spec["reduction"] / 100,
                description=spec["description"],
            ))
    return out


@router.get("/controls", response_model=list[ControlOption])
def controls(user: UserOut = Depends(current_user)):
    return _catalogue()


@router.post("/simulate", response_model=SimulationResponse)
def simulate(payload: SimulationRequest,
             user: UserOut = Depends(require_roles(Role.ANALYST, Role.CISO, Role.ADMIN))):
    catalogue = {c.control_id: c for c in _catalogue()}
    chosen = [catalogue[cid] for cid in payload.control_ids if cid in catalogue]
    if not chosen:
        raise HTTPException(status_code=400, detail="No recognised control IDs supplied.")

    summary = svc.executive_summary()
    eal = float(summary.get("total_expected_loss", 0) or 0)
    exposure = float(summary.get("var_95", 0) or 0)
    score = svc.overall_risk_score()

    # Controls overlap, so their reductions compose multiplicatively rather than
    # summing — four 30% controls reduce risk by 76%, not 120%.
    survival = 1.0
    for c in chosen:
        survival *= (1 - min(0.95, c.expected_risk_reduction_pct / 100))
    reduction = 1 - survival

    investment = sum(c.annual_cost for c in chosen)
    loss_avoided = eal * reduction
    rosi = (loss_avoided - investment) / investment if investment > 0 else 0.0

    after = SimulationState(
        risk_score=round(score * survival, 1),
        expected_annual_loss=round(eal * survival, 2),
        financial_exposure=round(exposure * survival, 2),
    )

    return SimulationResponse(
        controls_applied=chosen,
        before=SimulationState(risk_score=score, expected_annual_loss=eal,
                               financial_exposure=exposure),
        after=after,
        risk_reduction_pct=round(reduction * 100, 2),
        financial_loss_avoided=round(loss_avoided, 2),
        investment_cost=round(investment, 2),
        rosi=round(rosi, 2),
        payback_months=round(investment / (loss_avoided / 12), 1) if loss_avoided > 0 else None,
    )


@router.get("/precomputed")
def precomputed(user: UserOut = Depends(current_user)):
    """What-if scenarios computed by the pipeline's own FAIR re-runs."""
    return svc.graph_data().get("what_if_scenarios", [])
