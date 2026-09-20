import asyncio
import subprocess
import sys
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException

from .. import services as svc
from ..models import PipelineStatus, Role, UserOut
from ..security import current_user, require_roles

router = APIRouter(prefix="/api/v1/pipeline", tags=["pipeline"])

_lock = asyncio.Lock()
_state = None
_audit = None


def bind(run_state, audit_log):
    """Wired from main.py so the router shares one RunState with the scheduler."""
    global _state, _audit
    _state, _audit = run_state, audit_log


def _run_blocking(mode: str) -> dict:
    started = datetime.now()
    _state.mark_started()
    proc = subprocess.run(
        [sys.executable, str(svc.BASE_DIR / "main.py"), "--mode", mode],
        cwd=str(svc.BASE_DIR), capture_output=True, text=True,
    )
    detail = {"returncode": proc.returncode}
    if proc.returncode != 0:
        detail["stderr_tail"] = proc.stderr[-2000:]
    return _state.record_run(
        mode, "success" if proc.returncode == 0 else "failed",
        (datetime.now() - started).total_seconds(), detail,
    )


async def trigger(mode: str, force: bool) -> dict:
    if _lock.locked():
        raise HTTPException(status_code=409, detail="A pipeline run is already in progress.")
    async with _lock:
        if not force and not _state.inputs_changed():
            return {"status": "skipped",
                    "reason": "No source data changed since the last successful run."}
        if _audit:
            _audit.record("recompute_started", actor="api", detail={"mode": mode})
        result = await asyncio.to_thread(_run_blocking, mode)
        if _audit:
            _audit.record("recompute_finished", actor="api",
                          status=result.get("status", "unknown"), detail={"mode": mode})
        return result


@router.post("/recompute")
async def recompute(mode: str = "incremental", force: bool = True,
                    user: UserOut = Depends(require_roles(Role.CISO, Role.ADMIN))):
    if mode not in ("full", "incremental"):
        raise HTTPException(status_code=400, detail="mode must be 'full' or 'incremental'.")
    return await trigger(mode, force)


@router.get("/status", response_model=PipelineStatus)
def status(user: UserOut = Depends(current_user)):
    from ..main import REFRESH_INTERVAL_SECONDS

    return PipelineStatus(
        running=_lock.locked(),
        last_run=_state.last_run if _state else None,
        inputs_changed_since_last_run=_state.inputs_changed() if _state else False,
        refresh_interval_seconds=REFRESH_INTERVAL_SECONDS,
    )


@router.get("/runs")
def runs(user: UserOut = Depends(current_user)):
    return _state.history if _state else []


@router.get("/audit-log")
def audit_log(limit: int = 100,
              user: UserOut = Depends(require_roles(Role.CISO, Role.ADMIN))):
    return _audit.tail(limit) if _audit else []
