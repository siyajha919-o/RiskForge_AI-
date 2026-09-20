import os
import resource
from pathlib import Path

from fastapi import HTTPException, status


# ---------------------------------------------------------------------------
# 1. Path validation for /api/v1/dashboard/{section}
# ---------------------------------------------------------------------------
# Never use the raw path segment to build a filesystem path or dict lookup
# directly. Constrain it to a fixed allow-list instead.

ALLOWED_DASHBOARD_SECTIONS = {
    "risk-overview",
    "top-risks",
    "asset-risk",
    "vulnerability-summary",
    "investment-summary",
}


def validate_section(section: str) -> str:
    if section not in ALLOWED_DASHBOARD_SECTIONS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Unknown dashboard section.",
        )
    return section


# Usage:
#
#   @app.get("/api/v1/dashboard/{section}", dependencies=[Depends(verify_internal_secret)])
#   def dashboard_section(section: str):
#       section = validate_section(section)
#       # safe to use `section` now — it's guaranteed to be one of the
#       # known keys, never an arbitrary path/filename


# ---------------------------------------------------------------------------
# 2. Resource guard on the training/recompute path
# ---------------------------------------------------------------------------
# The per-process time-based guard in main_py_changes.md stops rapid repeat
# calls. This adds a memory ceiling for the training call itself, so a
# single (authenticated, correctly-spaced) call can't still exhaust the
# container. Linux-only (uses `resource`); skip/no-op on other platforms.

def apply_training_memory_limit(max_memory_mb: int = 1536) -> None:
    """Call once at process startup, before any training code can run."""
    try:
        max_bytes = max_memory_mb * 1024 * 1024
        resource.setrlimit(resource.RLIMIT_AS, (max_bytes, max_bytes))
    except (ValueError, OSError):
        # Not supported on this platform (e.g. Windows, some containers) —
        # rely on the docker-compose `deploy.resources.limits` instead.
        pass


# ---------------------------------------------------------------------------
# 3. Trusted-path-only model loading
# ---------------------------------------------------------------------------
# Keras/scikit-learn model files must only ever be loaded from a fixed,
# known directory — never a path built from request input, environment
# values the frontend could influence, or anything upload-derived.

MODEL_DIR = Path(os.environ.get("MODEL_DIR", "/app/models")).resolve()


def load_trusted_model_path(filename: str):
    """
    Returns a validated path inside MODEL_DIR, or raises. Use this instead
    of building a path from `filename` directly, even if `filename` is
    currently hardcoded in your own code — it keeps this safe if that
    ever changes.
    """
    candidate = (MODEL_DIR / filename).resolve()
    if MODEL_DIR not in candidate.parents and candidate != MODEL_DIR:
        raise ValueError(f"Rejected model path outside trusted directory: {filename}")
    if not candidate.is_file():
        raise FileNotFoundError(f"Model file not found: {candidate}")
    return candidate


# Usage:
#   model_path = load_trusted_model_path("risk_classifier.keras")
#   model = keras.models.load_model(model_path)
