"""
RISHFORGEAI — FastAPI application.

Serves the RiskForge dashboard. All computed figures originate from the FAIR
Monte Carlo engine in this repository; this layer only shapes and guards them.

Run:  uvicorn api.main:app --reload --port 8000
"""

import asyncio
import logging
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

# Load .env before anything reads os.environ, so the
# admin bootstrap values are available without exporting them by hand.
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    pass

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from src.audit import AuditLog          # noqa: E402
from src.run_state import RunState      # noqa: E402

from .routers import (                  # noqa: E402
    alerts, auth, compliance, dashboard, ingest, insights, investment, network,
    pipeline, remediation, reports, risk, scenarios, threats,
)
from .security import bootstrap_admin   # noqa: E402

log = logging.getLogger("riskforge")
logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")

DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "outputs"

REFRESH_INTERVAL_SECONDS = int(os.environ.get("RISK_REFRESH_INTERVAL_SECONDS", "300"))
FULL_RETRAIN_INTERVAL_SECONDS = int(os.environ.get("RISK_FULL_RETRAIN_INTERVAL_SECONDS", "86400"))

ALLOWED_ORIGINS = [
    o.strip() for o in os.environ.get(
        "CORS_ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
    ).split(",") if o.strip()
]

run_state = RunState(OUTPUT_DIR / "run_state.json", DATA_DIR)
audit = AuditLog(OUTPUT_DIR / "audit_log.jsonl")
pipeline.bind(run_state, audit)


async def _scheduler() -> None:
    """Recomputes only when source data actually changed — see src/run_state.py."""
    last_full = 0.0
    while True:
        try:
            await asyncio.sleep(REFRESH_INTERVAL_SECONDS)
            if not run_state.inputs_changed():
                continue
            now = asyncio.get_event_loop().time()
            mode = "full" if (now - last_full) > FULL_RETRAIN_INTERVAL_SECONDS else "incremental"
            if mode == "full":
                last_full = now
            log.info("Source data changed — starting %s recompute", mode)
            await pipeline.trigger(mode, force=True)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            log.error("Scheduled run failed: %s", exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    message = bootstrap_admin()
    if message:
        log.warning(message)
    if not OUTPUT_DIR.joinpath("graph_data.json").exists():
        log.warning("No computed results yet — run `python main.py --mode full` "
                    "or POST /api/v1/pipeline/recompute.")
    task = asyncio.create_task(_scheduler())
    yield
    task.cancel()


app = FastAPI(
    title="RISHFORGEAI — Cyber Risk Quantification API",
    description="AI-Powered Continuous Cyber Risk Quantification & Investment Optimization",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

for r in (auth, dashboard, risk, threats, scenarios, compliance,
          investment, network, reports, insights, pipeline, remediation, ingest,
          alerts):
    app.include_router(r.router)


@app.get("/", tags=["meta"])
def root():
    return JSONResponse({
        "service": "RISHFORGEAI API",
        "note": "This is the JSON API. The dashboard runs separately.",
        "dashboard_ui": "http://localhost:5173",
        "docs": "/docs",
        "health": "/health",
    })


@app.get("/health", tags=["meta"])
def health():
    return {
        "status": "ok",
        "results_available": OUTPUT_DIR.joinpath("graph_data.json").exists(),
        "last_run": run_state.last_run,
        "inputs_changed_since_last_run": run_state.inputs_changed(),
    }
