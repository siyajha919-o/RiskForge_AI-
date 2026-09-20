from fastapi import APIRouter, Depends, HTTPException

from .. import services as svc
from ..models import UserOut
from ..security import current_user
from src.alerts import AlertStore, evaluate, notify_webhook
from src.device_registry import DeviceRegistry

router = APIRouter(prefix="/api/v1/alerts", tags=["alerts"])

store = AlertStore(svc.OUTPUT_DIR / "alerts.json")
_registry = DeviceRegistry(
    store_path=svc.OUTPUT_DIR / "devices.json",
    csv_path=svc.DATA_DIR / "live_devices.csv",
)


def _current() -> list[dict]:
    """
    Re-evaluates against the latest computed output on every read.

    Cheap (a handful of comparisons over already-cached JSON) and it means the
    list is never stale after a recompute, without needing the pipeline to call
    back into the API.
    """
    alerts = evaluate(svc.graph_data())

    # Stale endpoint agents live in the device registry rather than graph_data,
    # so this rule is applied here where that store is available.
    try:
        summary = _registry.summary()
        stale = summary.get("stale") or 0
        if stale:
            alerts.append({
                "id": "stale_devices_0001",
                "rule": "stale_devices",
                "severity": "Medium",
                "title": f"{int(stale)} endpoint agent(s) not reporting",
                "detail": "Posture for these devices is unknown and may be out of date.",
                "value": int(stale),
                "acknowledged": False,
            })
    except Exception:  # noqa: BLE001 - a missing registry must not break alerts
        pass

    return store.sync(alerts)


@router.get("")
def list_alerts(unacknowledged_only: bool = False,
                user: UserOut = Depends(current_user)):
    _current()
    alerts = store.list(include_acknowledged=not unacknowledged_only)
    return {
        "alerts": alerts,
        "total": len(alerts),
        "unacknowledged": sum(1 for a in alerts if not a.get("acknowledged")),
    }


@router.post("/{alert_id}/ack")
def acknowledge(alert_id: str, user: UserOut = Depends(current_user)):
    updated = store.acknowledge(alert_id, actor=user.email)
    if not updated:
        raise HTTPException(status_code=404, detail="No such alert.")
    return updated


@router.post("/notify")
def notify(user: UserOut = Depends(current_user)):
    """
    Pushes current unacknowledged alerts to the configured webhook.

    No-ops with a clear message when RISKFORGE_WEBHOOK_URL is unset, rather than
    failing — delivery is opt-in.
    """
    sent = notify_webhook(_current())
    return {
        "delivered": sent,
        "detail": "Delivered." if sent
        else "No webhook configured (set RISKFORGE_WEBHOOK_URL), or nothing to send.",
    }
