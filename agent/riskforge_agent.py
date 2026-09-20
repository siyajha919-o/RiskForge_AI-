#!/usr/bin/env python3
"""
RiskForge endpoint agent.

Runs on a real machine and reports its own security posture to the risk engine,
so the platform ingests live telemetry instead of only static CSV exports. The
engine treats the reporting machine as a real asset: its open ports, patch
state, firewall and encryption status feed the same FAIR model as everything
else, and the scheduler recomputes exposure when the readings change.

Standard library only, so it runs on any machine with Python 3.8+ and no pip
install. Every probe degrades to None rather than failing — a laptop that can't
report firewall state still reports everything else.

Usage:
    python riskforge_agent.py --server http://<engine-host>:8000 --token <secret>
    python riskforge_agent.py --once          # single reading, then exit
"""

import argparse
import json
import os
import platform
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

AGENT_VERSION = "1.0.0"
COMMON_PORTS = [21, 22, 23, 25, 53, 80, 110, 135, 139, 143, 443, 445, 993, 995,
                1433, 1521, 3306, 3389, 5432, 5900, 6379, 8080, 8443, 9200, 27017]

# Ports that materially raise exposure if they're listening, and why.
RISKY_PORTS = {
    21: "FTP (cleartext credentials)",
    23: "Telnet (cleartext)",
    139: "NetBIOS",
    445: "SMB (ransomware vector)",
    3389: "RDP (brute-force target)",
    5900: "VNC",
    6379: "Redis (often unauthenticated)",
    9200: "Elasticsearch (often unauthenticated)",
    27017: "MongoDB (often unauthenticated)",
    1433: "MSSQL",
    3306: "MySQL",
    5432: "PostgreSQL",
}


def _run(cmd, timeout=6):
    """Run a probe command, returning stdout or None. Never raises."""
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                             shell=isinstance(cmd, str))
        return out.stdout.strip() if out.returncode == 0 else None
    except (subprocess.SubprocessError, OSError):
        return None


def listening_ports():
    """Locally reachable listening ports, by direct connect rather than parsing netstat."""
    open_ports = []
    for port in COMMON_PORTS:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(0.08)
        try:
            if s.connect_ex(("127.0.0.1", port)) == 0:
                open_ports.append(port)
        except OSError:
            pass
        finally:
            s.close()
    return open_ports


def firewall_enabled():
    system = platform.system()
    if system == "Darwin":
        out = _run(["/usr/libexec/ApplicationFirewall/socketfilterfw", "--getglobalstate"])
        return ("enabled" in out.lower()) if out else None
    if system == "Linux":
        out = _run(["ufw", "status"]) or _run(["firewall-cmd", "--state"])
        if out:
            return "active" in out.lower() or "running" in out.lower()
        return None
    if system == "Windows":
        out = _run(["netsh", "advfirewall", "show", "allprofiles", "state"])
        return ("ON" in out) if out else None
    return None


def disk_encrypted():
    system = platform.system()
    if system == "Darwin":
        out = _run(["fdesetup", "status"])
        return ("On" in out) if out else None
    if system == "Linux":
        out = _run("lsblk -o TYPE | grep -c crypt")
        try:
            return int(out) > 0 if out else None
        except ValueError:
            return None
    if system == "Windows":
        out = _run(["manage-bde", "-status", "C:"])
        return ("Percentage Encrypted: 100" in out) if out else None
    return None


def pending_updates():
    system = platform.system()
    if system == "Darwin":
        out = _run(["softwareupdate", "-l"], timeout=45)
        if out is None:
            return None
        if "No new software available" in out:
            return 0
        return sum(1 for line in out.splitlines() if line.strip().startswith("*"))
    if system == "Linux":
        out = _run("apt list --upgradable 2>/dev/null | tail -n +2 | wc -l", timeout=30)
        try:
            return int(out) if out else None
        except ValueError:
            return None
    return None


def failed_logins():
    system = platform.system()
    if system == "Darwin":
        out = _run('log show --predicate \'eventMessage CONTAINS "authentication failure"\' '
                   '--last 24h --style compact 2>/dev/null | wc -l', timeout=30)
    elif system == "Linux":
        out = _run("grep -ci 'authentication failure' /var/log/auth.log 2>/dev/null || echo 0")
    else:
        return None
    try:
        return int(out) if out else None
    except ValueError:
        return None


def uptime_hours():
    try:
        if platform.system() in ("Darwin", "Linux"):
            if os.path.exists("/proc/uptime"):
                with open("/proc/uptime") as f:
                    return round(float(f.read().split()[0]) / 3600, 1)
            out = _run(["sysctl", "-n", "kern.boottime"])
            if out and "sec = " in out:
                boot = int(out.split("sec = ")[1].split(",")[0])
                return round((time.time() - boot) / 3600, 1)
    except (OSError, ValueError, IndexError):
        pass
    return None


def local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))          # no packet sent; just picks the route
        return s.getsockname()[0]
    except OSError:
        return None
    finally:
        s.close()


# ---------------------------------------------------------------------------
# Android / Termux
#
# platform.system() reports "Linux" on Android, but almost none of the Linux
# probes apply — there is no ufw, no lsblk, no /var/log/auth.log. These read
# the Android property store instead, which gives two signals a laptop cannot:
# how stale the security patch level is, and whether the device is rooted.
# ---------------------------------------------------------------------------

def is_android():
    return bool(os.environ.get("ANDROID_ROOT") or os.environ.get("ANDROID_DATA")) \
        or os.path.exists("/system/build.prop")


def _getprop(key):
    out = _run(["getprop", key])
    return out or None


def android_patch_age_days():
    """
    Days since the OS security patch level. An unpatched phone accumulates
    known CVEs at a predictable rate, so this is the single most useful
    posture signal a handset reports.
    """
    patch = _getprop("ro.build.version.security_patch")
    if not patch:
        return None, None
    try:
        from datetime import date
        parts = [int(x) for x in patch.split("-")]
        patch_date = date(parts[0], parts[1], parts[2] if len(parts) > 2 else 1)
        return patch, (date.today() - patch_date).days
    except (ValueError, IndexError):
        return patch, None


def android_rooted():
    """Root breaks the OS security model outright — every app sandbox is void."""
    for path in ("/system/bin/su", "/system/xbin/su", "/sbin/su",
                 "/system/app/Superuser.apk", "/data/adb/magisk"):
        if os.path.exists(path):
            return True
    if _getprop("ro.debuggable") == "1":
        return True
    return False


def android_info():
    patch, patch_age = android_patch_age_days()
    release = _getprop("ro.build.version.release")

    eol = None
    if release:
        try:
            # Google stops shipping security fixes roughly three years after
            # a release; anything below 12 is out of support in 2026.
            eol = int(str(release).split(".")[0]) < 12
        except ValueError:
            eol = None

    return {
        "device_model": _getprop("ro.product.model"),
        "manufacturer": _getprop("ro.product.manufacturer"),
        "android_version": release,
        "android_eol": eol,
        "security_patch_level": patch,
        "security_patch_age_days": patch_age,
        "rooted": android_rooted(),
    }


def collect(asset_name=None, business_unit=None, criticality=None, environment="Production"):
    ports = listening_ports()
    risky = {p: RISKY_PORTS[p] for p in ports if p in RISKY_PORTS}

    android = android_info() if is_android() else {}

    return {
        "agent_version": AGENT_VERSION,
        "platform_kind": "android" if android else "desktop",
        **android,
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "hostname": socket.gethostname(),
        "asset_name": asset_name or socket.gethostname(),
        "business_unit_id": business_unit,
        "asset_criticality": criticality,
        "environment": environment,
        "operating_system": (f"Android {android['android_version']}" if android
                             else f"{platform.system()} {platform.release()}"),
        "os_version": platform.version(),
        "architecture": platform.machine(),
        "python_version": platform.python_version(),
        "local_ip": local_ip(),
        "uptime_hours": uptime_hours(),
        "listening_ports": ports,
        "risky_ports": risky,
        "open_port_count": len(ports),
        "firewall_enabled": firewall_enabled(),
        "disk_encrypted": disk_encrypted(),
        "pending_updates": pending_updates(),
        "failed_logins_24h": failed_logins(),
    }


def send(payload, server, token, verbose=True):
    url = server.rstrip("/") + "/api/v1/ingest/device"
    body = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("X-Agent-Token", token)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read())
        if verbose:
            print(f"  reported: risk_score={result.get('device_risk_score')} "
                  f"asset={result.get('asset_id')} findings={len(result.get('findings', []))}")
            for f in result.get("findings", []):
                print(f"    - {f}")
        return result
    except urllib.error.HTTPError as e:
        print(f"  rejected ({e.code}): {e.read().decode()[:200]}", file=sys.stderr)
    except urllib.error.URLError as e:
        print(f"  unreachable: {e.reason}", file=sys.stderr)
    return None


def main():
    p = argparse.ArgumentParser(description="RiskForge endpoint telemetry agent")
    p.add_argument("--server", default=os.environ.get("RISKFORGE_SERVER", "http://localhost:8000"))
    p.add_argument("--token", default=os.environ.get("RISKFORGE_AGENT_TOKEN", ""))
    p.add_argument("--interval", type=int, default=30, help="Seconds between reports")
    p.add_argument("--once", action="store_true", help="Send one reading and exit")
    p.add_argument("--name", help="Asset name (defaults to hostname)")
    p.add_argument("--business-unit", help="Business unit id, e.g. BU-0001")
    p.add_argument("--criticality", choices=["Low", "Medium", "High", "Critical"], default="High")
    p.add_argument("--environment", default="Production")
    p.add_argument("--dry-run", action="store_true", help="Print the reading, send nothing")
    args = p.parse_args()

    print(f"RiskForge agent {AGENT_VERSION} — {socket.gethostname()}")
    if not args.dry_run:
        print(f"reporting to {args.server} every {args.interval}s (Ctrl+C to stop)")

    while True:
        reading = collect(args.name, args.business_unit, args.criticality, args.environment)
        stamp = datetime.now().strftime("%H:%M:%S")
        if reading.get("platform_kind") == "android":
            print(f"[{stamp}] {reading.get('device_model')} "
                  f"Android {reading.get('android_version')} "
                  f"patch={reading.get('security_patch_level')} "
                  f"({reading.get('security_patch_age_days')}d old) "
                  f"rooted={reading.get('rooted')} "
                  f"ports={reading['open_port_count']}")
        else:
            print(f"[{stamp}] ports={reading['open_port_count']} "
                  f"risky={len(reading['risky_ports'])} "
                  f"firewall={reading['firewall_enabled']} "
                  f"encrypted={reading['disk_encrypted']} "
                  f"updates={reading['pending_updates']}")

        if args.dry_run:
            print(json.dumps(reading, indent=2))
            return
        send(reading, args.server, args.token)

        if args.once:
            return
        time.sleep(args.interval)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nstopped")
