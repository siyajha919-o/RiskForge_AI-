# Changes to apply in the RiskEngine's `api.py` / `main.py`

## 1. Replace the wide-open CORS config

**Before (per the review, `api.py:1-70`):**
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**After:**
```python
import os

allowed_origins = os.environ.get("RISKENGINE_ALLOWED_ORIGINS", "").split(",")
# In practice this should just be the Java backend's own origin, e.g.
# http://localhost:8080 or the backend's internal service URL — browsers
# should never call the RiskEngine directly at all.

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o for o in allowed_origins if o],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-Internal-Secret"],
)
```

## 2. Require the shared secret on the sensitive/expensive endpoint

```python
from fastapi import Depends
from security import verify_internal_secret

@app.post("/api/v1/recompute", dependencies=[Depends(verify_internal_secret)])
def recompute(...):
    ...

@app.get("/api/v1/recompute/status", dependencies=[Depends(verify_internal_secret)])
def recompute_status(...):
    ...
```

`/health` can stay open (useful for container/orchestrator health checks and
carries no sensitive data or side effects).

## 3. Rate-limit /recompute specifically

Training is expensive; even with the secret in place, add a minimal
per-process guard so a compromised backend credential (or a bug that
loops the call) can't hammer it:

```python
import time

_last_recompute_at = 0
_MIN_INTERVAL_SECONDS = 60  # tune to your actual training duration

@app.post("/api/v1/recompute", dependencies=[Depends(verify_internal_secret)])
def recompute(...):
    global _last_recompute_at
    now = time.time()
    if now - _last_recompute_at < _MIN_INTERVAL_SECONDS:
        raise HTTPException(status_code=429, detail="Recompute already in progress or ran too recently.")
    _last_recompute_at = now
    # ... existing training logic
```

## 4. Bind to localhost, not 0.0.0.0

If the RiskEngine and Java backend run on the same host/container network,
there's no reason to expose port 8000 externally at all:

```bash
uvicorn main:app --host 127.0.0.1 --port 8000
```

If they run in separate containers on the same Docker network, bind to
`0.0.0.0` inside the container but do **not** publish port 8000 to the host
in `docker-compose.yml` / `docker run -p` — only the Java backend's
container should be able to reach it, over the internal network.

## 5. On the Java side

Add the header to every outgoing call from the Java backend to the
RiskEngine (e.g. in the WebClient/RestTemplate config used to reach it):

```java
webClient.post()
    .uri(riskEngineUrl + "/api/v1/recompute")
    .header("X-Internal-Secret", riskEngineSharedSecret) // from env, same value as Python side
    .retrieve();
```
