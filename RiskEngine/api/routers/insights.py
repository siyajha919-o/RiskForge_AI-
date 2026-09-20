from fastapi import APIRouter, Depends, HTTPException

from .. import services as svc
from ..insights_store import list_insights, save_insight
from ..models import AskRequest, AskResponse, UserOut
from ..security import current_user

router = APIRouter(prefix="/api/v1", tags=["insights"])


@router.post("/ask", response_model=AskResponse)
def ask(payload: AskRequest, user: UserOut = Depends(current_user)):
    from src.ai_advisor import AIAdvisor

    advisor = AIAdvisor(svc.OUTPUT_DIR)
    try:
        result = advisor.answer(payload.question)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Advisor failed: {exc}")
    saved = save_insight(result)
    return AskResponse(**{k: v for k, v in saved.items() if k in AskResponse.model_fields})


@router.get("/insights/history")
def history(limit: int = 25, user: UserOut = Depends(current_user)):
    return list_insights(limit)


@router.get("/recommendations")
def recommendations(top_n: int = 5, user: UserOut = Depends(current_user)):
    from src.ai_advisor import AIAdvisor

    advisor = AIAdvisor(svc.OUTPUT_DIR)
    try:
        return advisor.explain_recommendations(top_n)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Advisor failed: {exc}")
