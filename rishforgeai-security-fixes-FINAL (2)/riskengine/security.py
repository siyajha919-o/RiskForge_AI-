

import os
import hmac

from fastapi import Header, HTTPException, status

RISK_ENGINE_SHARED_SECRET = os.environ.get("RISK_ENGINE_SHARED_SECRET")

if not RISK_ENGINE_SHARED_SECRET:
    raise RuntimeError(
        "RISK_ENGINE_SHARED_SECRET is not set. Set it to a long random value "
        "and configure the same value in the Java backend's outgoing request "
        "headers before starting the RiskEngine."
    )


def verify_internal_secret(x_internal_secret: str = Header(default="")) -> None:
    if not hmac.compare_digest(x_internal_secret, RISK_ENGINE_SHARED_SECRET):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authorized to call the risk engine directly.",
        )
