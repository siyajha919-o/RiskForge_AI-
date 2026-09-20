"""
Live endpoint device registry.

Receives telemetry from agents running on real machines and turns it into an
asset the risk engine treats like any other: the device's open ports, patch
backlog, firewall and encryption state become the inputs to its exposure.

This is what makes "continuous" literal rather than a scheduler re-reading the
same export. Because src/run_state.py fingerprints data/*.csv, writing the
device roster there is enough to make the next scheduled tick recompute — a
port opening on a laptop moves the enterprise risk figure on its own.
"""

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

_lock = threading.Lock()

# Weightings for the device posture score. Ports that expose a service to
# attack carry the most, because they are the only factor here that creates a
# remotely reachable entry point rather than weakening a local defence.
RISKY_PORT_WEIGHT = 12
OPEN_PORT_WEIGHT = 2
NO_FIREWALL_PENALTY = 18
NO_ENCRYPTION_PENALTY = 15
PENDING_UPDATE_WEIGHT = 3
FAILED_LOGIN_WEIGHT = 0.15

# Mobile-specific. Root voids the OS security model entirely, so it is weighted
# above any single misconfiguration. Patch age accrues gradually because risk
# from missing fixes compounds with time rather than arriving all at once.
ROOTED_PENALTY = 30
EOL_OS_PENALTY = 20
PATCH_AGE_WEIGHT = 0.05      # per day since the last security patch
PATCH_AGE_CAP = 25

# A device that stops reporting is not healthy — it is unmonitored.
STALE_AFTER_SECONDS = 300

CRITICALITY_WEIGHT = {"Low": 0.4, "Medium": 0.7, "High": 1.0, "Critical": 1.3}


class DeviceRegistry:
    def __init__(self, store_path: Path, csv_path: Path):
        self.store_path = Path(store_path)
        self.csv_path = Path(csv_path)

    # -- persistence ---------------------------------------------------

    def _load(self) -> Dict[str, Dict]:
        if not self.store_path.exists():
            return {}
        try:
            with open(self.store_path) as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except (json.JSONDecodeError, OSError):
            return {}

    def _save(self, devices: Dict[str, Dict]) -> None:
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.store_path, "w") as f:
            json.dump(devices, f, indent=2)

    # -- scoring -------------------------------------------------------

    @staticmethod
    def score(reading: Dict) -> Dict:
        """
        Posture score 0-100 (higher = riskier) plus the findings behind it.

        Every finding names the specific observation that caused it, so the
        number is explainable rather than a black box — the same standard the
        rest of the platform holds itself to.
        """
        score = 0.0
        findings: List[str] = []

        risky = reading.get("risky_ports") or {}
        if risky:
            score += RISKY_PORT_WEIGHT * len(risky)
            for port, why in risky.items():
                findings.append(f"Port {port} listening — {why}")

        open_count = int(reading.get("open_port_count") or 0)
        extra = max(0, open_count - len(risky))
        if extra:
            score += OPEN_PORT_WEIGHT * extra
            findings.append(f"{extra} additional listening port(s) widen the attack surface")

        if reading.get("firewall_enabled") is False:
            score += NO_FIREWALL_PENALTY
            findings.append("Host firewall disabled")

        if reading.get("disk_encrypted") is False:
            score += NO_ENCRYPTION_PENALTY
            findings.append("Disk not encrypted — data at rest exposed if the device is lost")

        updates = reading.get("pending_updates")
        if updates:
            score += min(PENDING_UPDATE_WEIGHT * int(updates), 20)
            findings.append(f"{updates} pending OS update(s)")

        failed = reading.get("failed_logins_24h")
        if failed and int(failed) > 20:
            score += min(FAILED_LOGIN_WEIGHT * int(failed), 15)
            findings.append(f"{failed} failed authentication attempts in 24h")

        # -- mobile endpoints ------------------------------------------
        if reading.get("rooted"):
            score += ROOTED_PENALTY
            findings.append("Device is rooted — the OS security model and app sandboxing are void")

        if reading.get("android_eol"):
            score += EOL_OS_PENALTY
            findings.append(
                f"Android {reading.get('android_version')} is past end-of-support — "
                "no further security patches are issued")

        patch_age = reading.get("security_patch_age_days")
        if patch_age and int(patch_age) > 90:
            score += min(PATCH_AGE_WEIGHT * int(patch_age), PATCH_AGE_CAP)
            years = int(patch_age) / 365
            findings.append(
                f"Security patch level is {patch_age} days old "
                f"({years:.1f} years of unpatched vulnerabilities)")

        weight = CRITICALITY_WEIGHT.get(reading.get("asset_criticality") or "High", 1.0)
        score = min(100.0, score * weight)

        if not findings:
            findings.append("No posture weaknesses detected")

        return {"device_risk_score": round(score, 1), "findings": findings}

    # -- ingest --------------------------------------------------------

    def record(self, reading: Dict) -> Dict:
        hostname = reading.get("hostname") or "unknown-host"
        asset_id = f"DEV-{hostname}"

        scored = self.score(reading)
        entry = {
            **reading,
            "asset_id": asset_id,
            "device_risk_score": scored["device_risk_score"],
            "findings": scored["findings"],
            "last_seen": datetime.now(timezone.utc).isoformat(),
        }

        with _lock:
            devices = self._load()
            previous = devices.get(asset_id, {})
            entry["first_seen"] = previous.get("first_seen", entry["last_seen"])
            entry["report_count"] = previous.get("report_count", 0) + 1
            # Surface movement, so the demo can point at what changed.
            if previous.get("device_risk_score") is not None:
                entry["previous_risk_score"] = previous["device_risk_score"]
                entry["risk_delta"] = round(
                    entry["device_risk_score"] - previous["device_risk_score"], 1)
            devices[asset_id] = entry
            self._save(devices)
            self._write_csv(devices)

        return entry

    def devices(self, include_stale: bool = True) -> List[Dict]:
        devices = list(self._load().values())
        now = datetime.now(timezone.utc)
        for d in devices:
            try:
                seen = datetime.fromisoformat(d.get("last_seen", ""))
                age = (now - seen).total_seconds()
            except (ValueError, TypeError):
                age = None
            d["seconds_since_report"] = round(age) if age is not None else None
            d["stale"] = (age is not None and age > STALE_AFTER_SECONDS)
        if not include_stale:
            devices = [d for d in devices if not d["stale"]]
        return sorted(devices, key=lambda d: -(d.get("device_risk_score") or 0))

    def summary(self) -> Dict:
        devices = self.devices()
        live = [d for d in devices if not d["stale"]]
        return {
            "total_devices": len(devices),
            "reporting": len(live),
            "stale": len(devices) - len(live),
            "avg_risk_score": round(sum(d.get("device_risk_score", 0) for d in devices) / len(devices), 1)
            if devices else 0,
            "highest_risk": devices[0]["asset_id"] if devices else None,
            "total_findings": sum(len(d.get("findings", [])) for d in devices),
        }

    # -- pipeline handoff ----------------------------------------------

    def _write_csv(self, devices: Dict[str, Dict]) -> None:
        """
        Write the roster in the assets.csv schema so the pipeline can append it
        to the estate. Writing here is also what trips the scheduler's change
        detection, closing the loop from device to recomputed exposure.
        """
        import csv

        columns = [
            "asset_id", "organization_id", "business_unit_id", "asset_name", "asset_type",
            "operating_system", "environment", "internet_exposed", "data_classification",
            "asset_criticality", "confidentiality_score", "integrity_score",
            "availability_score", "dependency_count", "asset_age_days", "current_risk_score",
            "device_risk_score", "open_port_count", "firewall_enabled", "disk_encrypted",
            "pending_updates", "last_seen",
        ]

        self.csv_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.csv_path, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
            w.writeheader()
            for d in devices.values():
                score = d.get("device_risk_score", 0)
                w.writerow({
                    "asset_id": d.get("asset_id"),
                    "organization_id": d.get("organization_id") or "ORG-001",
                    "business_unit_id": d.get("business_unit_id") or "BU-0001",
                    "asset_name": d.get("asset_name"),
                    "asset_type": "Mobile Device" if d.get("platform_kind") == "android" else "Managed Endpoint",
                    "operating_system": d.get("operating_system"),
                    "environment": d.get("environment") or "Production",
                    # A listening risky port is the observable proxy for reachability.
                    "internet_exposed": bool(d.get("risky_ports")),
                    "data_classification": "Confidential",
                    "asset_criticality": d.get("asset_criticality") or "High",
                    "confidentiality_score": 3 if d.get("disk_encrypted") else 8,
                    "integrity_score": 7,
                    "availability_score": 7,
                    "dependency_count": 1,
                    "asset_age_days": 1,
                    # assets.csv uses a 0-10 scale; the posture score is 0-100.
                    "current_risk_score": round(score / 10, 1),
                    "device_risk_score": score,
                    "open_port_count": d.get("open_port_count"),
                    "firewall_enabled": d.get("firewall_enabled"),
                    "disk_encrypted": d.get("disk_encrypted"),
                    "pending_updates": d.get("pending_updates"),
                    "last_seen": d.get("last_seen"),
                })
