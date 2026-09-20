from fastapi import APIRouter, Depends

from .. import services as svc
from ..models import (
    FrontierPoint, InvestmentRecommendation, OptimizationRequest,
    OptimizationResponse, UserOut,
)
from ..security import current_user

router = APIRouter(prefix="/api/v1/investment", tags=["investment"])


def _priority(rosi: float) -> str:
    if rosi >= 5:
        return "Critical"
    if rosi >= 2:
        return "High"
    if rosi >= 0.5:
        return "Medium"
    return "Low"


@router.post("/optimize", response_model=OptimizationResponse)
def optimize(payload: OptimizationRequest, user: UserOut = Depends(current_user)):
    """
    Budget-constrained control selection.

    Greedy by loss-avoided-per-rupee, which is the standard 0/1-knapsack
    approximation and stays stable as the user drags the budget — a re-solved
    exact knapsack can reshuffle the whole list for a small budget change,
    which reads as instability rather than insight.
    """
    budget = payload.budget
    options = svc.investment_options()
    eal = float(svc.executive_summary().get("total_expected_loss", 0) or 0)

    candidates = []
    if not options.empty:
        for r in options.to_dict("records"):
            cost = float(r.get("implementation_cost", 0) or 0) + float(r.get("annual_operating_cost", 0) or 0)
            if cost <= 0:
                continue
            reduction = float(r.get("expected_risk_reduction_percentage", 0) or 0)
            avoided = float(r.get("expected_loss_reduction", 0) or 0) or (eal * reduction / 100)
            candidates.append({
                "control_id": str(r.get("control_id", r.get("investment_id", ""))),
                "name": str(r.get("investment_name", "Security control")),
                "category": None,
                "cost": cost,
                "reduction": reduction,
                "avoided": avoided,
            })

    if not candidates:
        controls = svc.controls()
        for r in controls.to_dict("records"):
            cost = float(r.get("annual_cost", 0) or 0)
            if cost <= 0:
                continue
            reduction = float(r.get("risk_reduction_percentage", 0) or 0)
            candidates.append({
                "control_id": str(r.get("control_id", "")),
                "name": str(r.get("control_name", "Security control")),
                "category": str(r.get("control_category", "")) or None,
                "cost": cost,
                "reduction": reduction,
                "avoided": eal * reduction / 100,
            })

    for c in candidates:
        c["efficiency"] = c["avoided"] / c["cost"] if c["cost"] else 0
    candidates.sort(key=lambda c: -c["efficiency"])

    spent = 0.0
    survival = 1.0
    recommendations = []
    for c in candidates[:60]:
        selected = spent + c["cost"] <= budget
        if selected:
            spent += c["cost"]
            survival *= (1 - min(0.95, c["reduction"] / 100))
        rosi = (c["avoided"] - c["cost"]) / c["cost"] if c["cost"] else 0
        recommendations.append(InvestmentRecommendation(
            control_id=c["control_id"],
            name=c["name"],
            category=c["category"],
            investment_cost=round(c["cost"], 2),
            expected_risk_reduction_pct=round(c["reduction"], 2),
            financial_loss_avoided=round(c["avoided"], 2),
            rosi=round(rosi, 2),
            roi_pct=round(rosi * 100, 2),
            priority=_priority(rosi),
            selected=selected,
        ))

    total_reduction = (1 - survival) * 100
    total_avoided = eal * (1 - survival)

    # Frontier: re-run the same greedy selection at increasing budget fractions.
    frontier = []
    for fraction in [i / 20 for i in range(1, 21)]:
        b = budget * fraction
        s, surv = 0.0, 1.0
        for c in candidates[:60]:
            if s + c["cost"] <= b:
                s += c["cost"]
                surv *= (1 - min(0.95, c["reduction"] / 100))
        if s > 0:
            avoided = eal * (1 - surv)
            frontier.append(FrontierPoint(
                investment=round(s, 2),
                risk_reduction_pct=round((1 - surv) * 100, 2),
                rosi=round((avoided - s) / s, 2),
                is_optimal=abs(fraction - 1.0) < 1e-9,
            ))

    return OptimizationResponse(
        budget=budget,
        total_allocated=round(spent, 2),
        unallocated=round(budget - spent, 2),
        total_risk_reduction_pct=round(total_reduction, 2),
        total_loss_avoided=round(total_avoided, 2),
        portfolio_rosi=round((total_avoided - spent) / spent, 2) if spent else 0.0,
        recommendations=recommendations,
        frontier=frontier,
    )


@router.get("/frontier")
def pipeline_frontier(user: UserOut = Depends(current_user)):
    """The efficient frontier the pipeline computed with PuLP."""
    return svc.graph_data().get("efficient_frontier", [])
