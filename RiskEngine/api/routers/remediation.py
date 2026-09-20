from fastapi import APIRouter, Depends, Query

from .. import services as svc
from ..models import RemediationAction, RemediationBacklog, RemediationResponse, UserOut
from ..security import current_user

router = APIRouter(prefix="/api/v1/remediation", tags=["remediation"])


@router.get("", response_model=RemediationResponse)
def remediation(limit: int = Query(25, ge=1, le=200), user: UserOut = Depends(current_user)):
    """
    Prioritized mitigation actions and backlog health.

    Ordering is by expected loss reduction per rupee, not by the source data's
    Critical/High/Medium/Low label — replacing that qualitative ranking with a
    financial one is the point of the platform.
    """
    return RemediationResponse(
        recommendations=[RemediationAction(**r) for r in svc.remediation_recommendations(limit)],
        backlog=RemediationBacklog(**(svc.remediation_backlog() or {})),
    )


@router.get("/backlog", response_model=RemediationBacklog)
def backlog(user: UserOut = Depends(current_user)):
    return RemediationBacklog(**(svc.remediation_backlog() or {}))
