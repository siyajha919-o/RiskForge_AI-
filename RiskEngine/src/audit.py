"""
Append-only audit log.

A cyber risk platform mapped to RBI CSF / SEBI CSCRF / ISO 27001 is expected to
answer "who did what, when" about its own operation — not just about the assets
it monitors. This records the actions that change reported risk: recompute
triggers, scenario runs, and report generation.

JSONL rather than a table so it stays append-only and greppable, and so a
partially-written line can never corrupt earlier entries.
"""

import json
import threading
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

_lock = threading.Lock()

# Never write these into the log, at any nesting depth.
_REDACT_KEYS = {"secret", "password", "token", "api_key", "authorization", "x_internal_secret"}


def _redact(value):
    if isinstance(value, dict):
        return {
            k: ("***" if k.lower().replace("-", "_") in _REDACT_KEYS else _redact(v))
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [_redact(v) for v in value]
    return value


class AuditLog:
    def __init__(self, path: Path):
        self.path = Path(path)

    def record(
        self,
        action: str,
        actor: str = "system",
        status: str = "ok",
        detail: Optional[Dict] = None,
    ) -> Dict:
        entry = {
            "timestamp": datetime.now().isoformat(),
            "actor": actor,
            "action": action,
            "status": status,
            "detail": _redact(detail or {}),
        }
        with _lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.path, "a") as f:
                f.write(json.dumps(entry) + "\n")
        return entry

    def tail(self, limit: int = 100) -> List[Dict]:
        if not self.path.exists():
            return []
        with open(self.path) as f:
            lines = f.readlines()
        out = []
        for line in lines[-limit:]:
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return list(reversed(out))
