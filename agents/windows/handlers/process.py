import os
import subprocess
from pathlib import Path

import psutil


def is_process_running(name: str) -> bool:
    target = name.lower()
    for proc in psutil.process_iter():
        try:
            if proc.name().lower() == target:
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            # Process exited mid-scan, or is a protected/system process we
            # can't query -- neither means "not the one we're looking for",
            # so skip it rather than let one flaky process fail the scan.
            continue
    return False


def start_process(path: str) -> None:
    subprocess.Popen([path])


def kill_process(name: str) -> None:
    target = name.lower()
    for proc in psutil.process_iter():
        try:
            if proc.name().lower() == target:
                proc.terminate()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue


def handle_launch_app(params: dict) -> dict:
    try:
        subprocess.Popen(params["path"])
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def handle_force_stop(params: dict, item_type: str | None = None) -> dict:
    try:
        process_name = params.get("process_name")

        # Deriving from the original item's own type/params instead of
        # requiring a dedicated stored field means force-stop works
        # immediately on every existing item, with zero manual data entry
        # via Studio Mode.
        if process_name is None:
            if item_type == "launch_app" and params.get("path"):
                process_name = os.path.basename(params["path"])
            elif item_type == "process_toggle":
                # Same env lookup handle_process_toggle uses -- read here,
                # not at module level, for the same load_dotenv() ordering
                # reason as handle_process_toggle below.
                process_name = os.environ["VPN_PROCESS_NAME"]
            else:
                return {
                    "status": "error",
                    "message": "no process identifiable for force stop on this item type",
                }

        # kill_process() is already a no-op if nothing matches, so this is
        # idempotent by construction -- "ok" regardless of whether anything
        # was actually running.
        kill_process(process_name)
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def handle_process_toggle(params: dict) -> dict:
    try:
        # Read here, not at module level: agent.py imports handlers before
        # calling load_dotenv(), so these wouldn't be populated yet if read
        # at import time in this file (same reasoning as SERVER_IP/PORT and
        # OUTPUT_DEVICE_PRIMARY/SECONDARY in the other handlers).
        vpn_process_name = os.environ["VPN_PROCESS_NAME"]
        vpn_path = os.environ["VPN_PATH"]

        if is_process_running(vpn_process_name):
            kill_process(vpn_process_name)
        else:
            # Checked explicitly rather than letting Popen raise: a bad
            # VPN_PATH should come back as a clear message, not a raw
            # FileNotFoundError traceback string.
            if not Path(vpn_path).exists():
                return {"status": "error", "message": f"VPN_PATH does not exist: {vpn_path}"}
            start_process(vpn_path)
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "message": str(e)}
