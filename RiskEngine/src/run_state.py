

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


class RunState:
    def __init__(self, state_path: Path, data_path: Path, history_limit: int = 50):
        self.state_path = Path(state_path)
        self.data_path = Path(data_path)
        self.history_limit = history_limit
        self._state = self._load()

    def _load(self) -> Dict:
        if self.state_path.exists():
            try:
                with open(self.state_path) as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                pass
        return {"last_run": None, "input_fingerprint": None, "history": []}

    def _save(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.state_path, "w") as f:
            json.dump(self._state, f, indent=2)

    def fingerprint_inputs(self) -> str:
        """
        Hash of (filename, size, mtime) for every source CSV. Cheap enough to
        run every tick on 200k+ rows, since it never opens the files.
        """
        digest = hashlib.sha256()
        for csv_file in sorted(self.data_path.glob("*.csv")):
            stat = csv_file.stat()
            digest.update(f"{csv_file.name}:{stat.st_size}:{int(stat.st_mtime)}".encode())
        return digest.hexdigest()

    def inputs_changed(self) -> bool:
        return self.fingerprint_inputs() != self._state.get("input_fingerprint")

    def record_run(
        self,
        mode: str,
        status: str,
        duration_seconds: float,
        detail: Optional[Dict] = None,
    ) -> Dict:
        entry = {
            "started_at": self._state.get("_pending_start"),
            "finished_at": datetime.now().isoformat(),
            "mode": mode,
            "status": status,
            "duration_seconds": round(duration_seconds, 2),
            "detail": detail or {},
        }

        if status == "success":
            self._state["input_fingerprint"] = self.fingerprint_inputs()
            self._state["last_run"] = entry

        history: List[Dict] = self._state.get("history", [])
        history.insert(0, entry)
        self._state["history"] = history[: self.history_limit]
        self._state.pop("_pending_start", None)
        self._save()
        return entry

    def mark_started(self) -> None:
        self._state["_pending_start"] = datetime.now().isoformat()
        self._save()

    @property
    def last_run(self) -> Optional[Dict]:
        return self._state.get("last_run")

    @property
    def history(self) -> List[Dict]:
        return self._state.get("history", [])
