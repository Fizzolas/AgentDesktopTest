# monitor.py
# Role: System health monitor. Tracks Ollama status, memory usage, GPU stats, and agent runtime state.
# Imports from: config.py, agent_loop.py (lazy import), psutil, requests, time, threading, os, sys, json, pathlib, datetime
# Contract: start_monitoring() -> None
#           stop_monitoring() -> None
#           get_current_status() -> dict
#           get_dashboard_status() -> dict
# Output: Continuous rolling log file (monitor.log) with timestamped diagnostic info

from __future__ import annotations

import os
import sys
import time
import json
import psutil
import requests
import threading
from datetime import datetime
from pathlib import Path

from config import OLLAMA_URL, MODEL_NAME, DEBUG

# =============================================================================
# Monitor Configuration
# =============================================================================
LOG_FILE = Path("monitor.log")
MONITOR_INTERVAL = 5.0
MAX_LOG_SIZE = 10 * 1024 * 1024

# Internal state
_monitoring = False
_monitor_thread = None


def _get_timestamp() -> str:
    """Returns formatted timestamp for log entries."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")



def _rotate_log_if_needed() -> None:
    """Rotates log file if it exceeds MAX_LOG_SIZE."""
    if LOG_FILE.exists() and LOG_FILE.stat().st_size > MAX_LOG_SIZE:
        backup = LOG_FILE.with_suffix(".log.old")
        if backup.exists():
            backup.unlink()
        LOG_FILE.rename(backup)
        _log_message("INFO", "Log rotated due to size limit")



def _log_message(level: str, message: str, data: dict | None = None) -> None:
    """Writes a timestamped message to the log file."""
    timestamp = _get_timestamp()
    log_entry = f"[{timestamp}] [{level}] {message}"
    if data:
        log_entry += f" | {json.dumps(data)}"

    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(log_entry + "\n")

    if DEBUG:
        print(log_entry)



def _check_ollama_status() -> dict:
    """Checks Ollama server health and returns status dict."""
    status = {
        "reachable": False,
        "response_time_ms": None,
        "error": None,
    }

    try:
        start = time.time()
        response = requests.get(OLLAMA_URL, timeout=3)
        elapsed = (time.time() - start) * 1000

        status["reachable"] = response.status_code == 200
        status["response_time_ms"] = round(elapsed, 2)

        if response.status_code != 200:
            status["error"] = f"HTTP {response.status_code}"
    except requests.exceptions.Timeout:
        status["error"] = "Timeout (>3s)"
    except requests.exceptions.ConnectionError:
        status["error"] = "Connection refused"
    except Exception as e:
        status["error"] = str(e)

    return status



def _check_ollama_model_status() -> dict:
    """Checks if the target model is loaded in Ollama."""
    status = {
        "model_loaded": False,
        "error": None,
    }

    try:
        response = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        if response.status_code == 200:
            data = response.json()
            models = [m["name"] for m in data.get("models", [])]
            status["model_loaded"] = MODEL_NAME in models
            if not status["model_loaded"]:
                status["error"] = f"Model '{MODEL_NAME}' not found in Ollama"
        else:
            status["error"] = f"HTTP {response.status_code}"
    except Exception as e:
        status["error"] = str(e)

    return status



def _get_system_stats() -> dict:
    """Collects system resource usage stats."""
    try:
        cpu_percent = psutil.cpu_percent(interval=0.5)

        ram = psutil.virtual_memory()
        ram_used_gb = ram.used / (1024 ** 3)
        ram_total_gb = ram.total / (1024 ** 3)
        ram_percent = ram.percent

        disk = psutil.disk_usage(os.getcwd())
        disk_free_gb = disk.free / (1024 ** 3)

        gpu_stats = _get_gpu_stats()

        return {
            "cpu_percent": round(cpu_percent, 1),
            "ram_used_gb": round(ram_used_gb, 2),
            "ram_total_gb": round(ram_total_gb, 2),
            "ram_percent": round(ram_percent, 1),
            "disk_free_gb": round(disk_free_gb, 2),
            "gpu": gpu_stats,
        }
    except Exception as e:
        return {"error": str(e)}



def _get_gpu_stats() -> dict:
    """Attempts to get NVIDIA GPU stats via nvidia-smi."""
    try:
        import subprocess

        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=utilization.gpu,memory.used,memory.total,temperature.gpu",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=2,
        )
        if result.returncode == 0:
            parts = result.stdout.strip().split(", ")
            return {
                "utilization_percent": int(parts[0]),
                "vram_used_mb": int(parts[1]),
                "vram_total_mb": int(parts[2]),
                "temperature_c": int(parts[3]),
            }
    except Exception:
        pass

    return {"available": False}



def _get_python_process_stats() -> dict:
    """Gets stats for the current Python process."""
    try:
        process = psutil.Process(os.getpid())
        return {
            "pid": process.pid,
            "memory_mb": round(process.memory_info().rss / (1024 ** 2), 2),
            "cpu_percent": round(process.cpu_percent(interval=0.1), 1),
            "threads": process.num_threads(),
        }
    except Exception as e:
        return {"error": str(e)}



def _get_runtime_status() -> dict:
    """
    Attempts to retrieve the current typed runtime session snapshot.
    Lazy import avoids forcing monitor.py to bootstrap the runtime when used standalone.
    """
    try:
        import agent_loop

        snapshot = agent_loop.get_session_snapshot()
        if not snapshot.get("active"):
            return {
                "available": True,
                "active": False,
                "running": snapshot.get("running", False),
                "status": "idle",
                "goal": "",
                "pending_task_count": 0,
                "completed_task_count": 0,
                "failed_task_count": 0,
                "last_action": snapshot.get("last_action", ""),
                "last_screen_description": "",
            }

        last_screen_state = snapshot.get("last_screen_state") or {}
        return {
            "available": True,
            "active": True,
            "running": snapshot.get("running", False),
            "session_id": snapshot.get("session_id", ""),
            "status": snapshot.get("status", "unknown"),
            "goal": snapshot.get("goal", ""),
            "active_model": snapshot.get("active_model", ""),
            "pending_task_count": snapshot.get("pending_task_count", 0),
            "completed_task_count": snapshot.get("completed_task_count", 0),
            "failed_task_count": snapshot.get("failed_task_count", 0),
            "last_action": snapshot.get("last_action", ""),
            "last_screen_description": last_screen_state.get("description", ""),
            "notes_count": len(snapshot.get("notes", [])),
        }
    except Exception as e:
        return {
            "available": False,
            "active": False,
            "running": False,
            "status": "unavailable",
            "error": str(e),
        }



def _build_health_flags(
    ollama_status: dict,
    model_status: dict,
    system_stats: dict,
    runtime_status: dict,
) -> list[str]:
    flags: list[str] = []

    if not ollama_status.get("reachable"):
        flags.append("backend_down")
    elif (ollama_status.get("response_time_ms") or 0) > 1000:
        flags.append("backend_slow")

    if not model_status.get("model_loaded"):
        flags.append("model_unavailable")

    if system_stats.get("ram_percent", 0) > 90:
        flags.append("high_ram")

    gpu = system_stats.get("gpu", {})
    if gpu.get("available") is not False:
        if gpu.get("utilization_percent", 0) > 95:
            flags.append("high_gpu")
        if gpu.get("temperature_c", 0) > 85:
            flags.append("high_gpu_temp")

    if runtime_status.get("available") and runtime_status.get("running"):
        if runtime_status.get("failed_task_count", 0) > 0:
            flags.append("runtime_task_failures")
        if runtime_status.get("pending_task_count", 0) > 10:
            flags.append("runtime_queue_backlog")

    return flags



def _build_status_summary(
    ollama_status: dict,
    model_status: dict,
    runtime_status: dict,
    flags: list[str],
) -> str:
    if flags:
        return f"Attention needed: {', '.join(flags)}"

    if runtime_status.get("running"):
        goal = runtime_status.get("goal", "")
        if goal:
            return f"Runtime active on goal: {goal[:80]}"
        return "Runtime active"

    if ollama_status.get("reachable") and model_status.get("model_loaded"):
        return "System ready"

    return "Monitoring active"



def _log_runtime_warnings(runtime_status: dict, flags: list[str]) -> None:
    if not runtime_status.get("available"):
        _log_message("WARN", "Runtime snapshot unavailable", runtime_status)
        return

    if runtime_status.get("running") and "runtime_task_failures" in flags:
        _log_message("WARN", "Runtime task failures detected", runtime_status)

    if runtime_status.get("running") and "runtime_queue_backlog" in flags:
        _log_message("WARN", "Runtime queue backlog detected", runtime_status)



def _monitor_loop() -> None:
    """Main monitoring loop - runs in background thread."""
    global _monitoring

    _log_message("INFO", "Monitor started", {"interval_sec": MONITOR_INTERVAL})

    while _monitoring:
        try:
            _rotate_log_if_needed()

            ollama_status = _check_ollama_status()
            model_status = _check_ollama_model_status()
            system_stats = _get_system_stats()
            process_stats = _get_python_process_stats()
            runtime_status = _get_runtime_status()
            health_flags = _build_health_flags(
                ollama_status=ollama_status,
                model_status=model_status,
                system_stats=system_stats,
                runtime_status=runtime_status,
            )

            if not ollama_status["reachable"]:
                _log_message("ERROR", "Ollama unreachable", ollama_status)
            elif ollama_status["response_time_ms"] and ollama_status["response_time_ms"] > 1000:
                _log_message("WARN", "Ollama slow response", ollama_status)

            if model_status.get("error"):
                _log_message("WARN", "Model status issue", model_status)

            if system_stats.get("ram_percent", 0) > 90:
                _log_message("WARN", "High RAM usage", {"ram_percent": system_stats["ram_percent"]})

            gpu = system_stats.get("gpu", {})
            if gpu.get("available") is not False:
                if gpu.get("utilization_percent", 0) > 95:
                    _log_message("WARN", "High GPU utilization", gpu)
                if gpu.get("temperature_c", 0) > 85:
                    _log_message("WARN", "High GPU temperature", gpu)

            _log_runtime_warnings(runtime_status, health_flags)

            if int(time.time()) % 25 < MONITOR_INTERVAL:
                snapshot = {
                    "summary": _build_status_summary(
                        ollama_status=ollama_status,
                        model_status=model_status,
                        runtime_status=runtime_status,
                        flags=health_flags,
                    ),
                    "health_flags": health_flags,
                    "ollama": ollama_status,
                    "model": model_status,
                    "system": system_stats,
                    "process": process_stats,
                    "runtime": runtime_status,
                }
                _log_message("INFO", "Status snapshot", snapshot)

        except Exception as e:
            _log_message("ERROR", f"Monitor loop exception: {e}")

        time.sleep(MONITOR_INTERVAL)

    _log_message("INFO", "Monitor stopped")



def start_monitoring() -> None:
    """Starts the background monitoring thread."""
    global _monitoring, _monitor_thread

    if _monitoring:
        print("[monitor] Already running.")
        return

    _monitoring = True
    _monitor_thread = threading.Thread(target=_monitor_loop, daemon=True)
    _monitor_thread.start()

    print(f"[monitor] Started. Logging to {LOG_FILE.absolute()}")



def stop_monitoring() -> None:
    """Stops the background monitoring thread."""
    global _monitoring

    if not _monitoring:
        return

    _monitoring = False
    if _monitor_thread:
        _monitor_thread.join(timeout=MONITOR_INTERVAL + 1)

    print("[monitor] Stopped.")



def get_current_status() -> dict:
    """Returns full current system + runtime status snapshot (synchronous call)."""
    ollama_status = _check_ollama_status()
    model_status = _check_ollama_model_status()
    system_stats = _get_system_stats()
    process_stats = _get_python_process_stats()
    runtime_status = _get_runtime_status()
    health_flags = _build_health_flags(
        ollama_status=ollama_status,
        model_status=model_status,
        system_stats=system_stats,
        runtime_status=runtime_status,
    )

    return {
        "timestamp": _get_timestamp(),
        "summary": _build_status_summary(
            ollama_status=ollama_status,
            model_status=model_status,
            runtime_status=runtime_status,
            flags=health_flags,
        ),
        "health_flags": health_flags,
        "ollama": ollama_status,
        "model": model_status,
        "system": system_stats,
        "process": process_stats,
        "runtime": runtime_status,
    }



def get_dashboard_status() -> dict:
    """
    Returns a compact UI-friendly status payload for future shell/GUI surfaces.
    """
    status = get_current_status()
    runtime_status = status.get("runtime", {})
    system_stats = status.get("system", {})
    gpu = system_stats.get("gpu", {})

    return {
        "timestamp": status.get("timestamp", ""),
        "summary": status.get("summary", ""),
        "health_flags": status.get("health_flags", []),
        "backend_reachable": status.get("ollama", {}).get("reachable", False),
        "model_loaded": status.get("model", {}).get("model_loaded", False),
        "runtime_running": runtime_status.get("running", False),
        "runtime_status": runtime_status.get("status", "unknown"),
        "goal": runtime_status.get("goal", ""),
        "pending_task_count": runtime_status.get("pending_task_count", 0),
        "completed_task_count": runtime_status.get("completed_task_count", 0),
        "failed_task_count": runtime_status.get("failed_task_count", 0),
        "last_screen_description": runtime_status.get("last_screen_description", ""),
        "cpu_percent": system_stats.get("cpu_percent"),
        "ram_percent": system_stats.get("ram_percent"),
        "gpu_utilization_percent": gpu.get("utilization_percent") if gpu.get("available") is not False else None,
        "gpu_temperature_c": gpu.get("temperature_c") if gpu.get("available") is not False else None,
    }


if __name__ == "__main__":
    print("=" * 60)
    print(" AgentDesktopTest Monitor")
    print(f" Ollama: {OLLAMA_URL}")
    print(f" Model : {MODEL_NAME}")
    print(f" Log   : {LOG_FILE.absolute()}")
    print("=" * 60)
    print("\nPress Ctrl+C to stop.\n")

    start_monitoring()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[monitor] Shutting down...")
        stop_monitoring()
        sys.exit(0)
