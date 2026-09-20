import hmac
import os

from fastapi import APIRouter, Depends, Header, HTTPException

from .. import services as svc
from ..models import UserOut
from ..security import current_user
from src.audit import AuditLog
from src.device_registry import DeviceRegistry

router = APIRouter(prefix="/api/v1", tags=["ingest"])

registry = DeviceRegistry(
    store_path=svc.OUTPUT_DIR / "devices.json",
    csv_path=svc.DATA_DIR / "live_devices.csv",
)
audit = AuditLog(svc.OUTPUT_DIR / "audit_log.jsonl")

# Agents authenticate with a shared token rather than a user session — they run
# unattended. Unset means open ingest, which is fine on a laptop demo but is
# logged loudly so it is never mistaken for a deployed default.
AGENT_TOKEN = os.environ.get("RISKFORGE_AGENT_TOKEN", "")


def verify_agent(x_agent_token: str = Header(default="")) -> None:
    if not AGENT_TOKEN:
        return
    if not hmac.compare_digest(x_agent_token, AGENT_TOKEN):
        raise HTTPException(status_code=401, detail="Invalid or missing X-Agent-Token.")


@router.post("/ingest/device", dependencies=[Depends(verify_agent)])
def ingest_device(reading: dict):
    """
    Accept one telemetry reading from an endpoint agent.

    Returns the scored posture immediately so the agent can print what changed,
    and writes the device roster to data/live_devices.csv — which the pipeline's
    change detection picks up on its next tick.
    """
    if not reading.get("hostname"):
        raise HTTPException(status_code=400, detail="Reading must include a hostname.")

    entry = registry.record(reading)
    audit.record(
        "device_telemetry",
        actor=entry["asset_id"],
        detail={
            "risk_score": entry["device_risk_score"],
            "delta": entry.get("risk_delta"),
            "open_ports": entry.get("open_port_count"),
        },
    )
    return {
        "asset_id": entry["asset_id"],
        "device_risk_score": entry["device_risk_score"],
        "risk_delta": entry.get("risk_delta"),
        "findings": entry["findings"],
        "report_count": entry["report_count"],
    }


@router.get("/devices")
def devices(user: UserOut = Depends(current_user)):
    """Live endpoint fleet — reported posture, findings, and staleness."""
    return {"summary": registry.summary(), "devices": registry.devices()}
