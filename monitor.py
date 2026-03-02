# monitor.py
# Role: System health monitor. Tracks Ollama status, memory usage, GPU stats, and agent loop state.
# Imports from: config.py, psutil, requests, time, threading, os
# Contract: start_monitoring() -> None
#           stop_monitoring() -> None
#           get_current_status() -> dict
# Output: Continuous rolling log file (monitor.log) with timestamped diagnostic info

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
MONITOR_INTERVAL = 5.0  # seconds between status checks
MAX_LOG_SIZE = 10 * 1024 * 1024  # 10MB - rotate log when exceeded

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


def _log_message(level: str, message: str, data: dict = None) -> None:
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
        # CPU
        cpu_percent = psutil.cpu_percent(interval=0.5)
        
        # RAM
        ram = psutil.virtual_memory()
        ram_used_gb = ram.used / (1024 ** 3)
        ram_total_gb = ram.total / (1024 ** 3)
        ram_percent = ram.percent
        
        # Disk (project directory)
        disk = psutil.disk_usage(os.getcwd())
        disk_free_gb = disk.free / (1024 ** 3)
        
        # GPU (NVIDIA only - via nvidia-smi if available)
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
            ["nvidia-smi", "--query-gpu=utilization.gpu,memory.used,memory.total,temperature.gpu", "--format=csv,noheader,nounits"],
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


def _monitor_loop() -> None:
    """Main monitoring loop - runs in background thread."""
    global _monitoring
    
    _log_message("INFO", "Monitor started", {"interval_sec": MONITOR_INTERVAL})
    
    while _monitoring:
        try:
            _rotate_log_if_needed()
            
            # Collect all diagnostics
            ollama_status = _check_ollama_status()
            model_status = _check_ollama_model_status()
            system_stats = _get_system_stats()
            process_stats = _get_python_process_stats()
            
            # Log Ollama issues
            if not ollama_status["reachable"]:
                _log_message("ERROR", "Ollama unreachable", ollama_status)
            elif ollama_status["response_time_ms"] and ollama_status["response_time_ms"] > 1000:
                _log_message("WARN", "Ollama slow response", ollama_status)
            
            if model_status.get("error"):
                _log_message("WARN", "Model status issue", model_status)
            
            # Log resource warnings
            if system_stats.get("ram_percent", 0) > 90:
                _log_message("WARN", "High RAM usage", {"ram_percent": system_stats["ram_percent"]})
            
            gpu = system_stats.get("gpu", {})
            if gpu.get("available") is not False:
                if gpu.get("utilization_percent", 0) > 95:
                    _log_message("WARN", "High GPU utilization", gpu)
                if gpu.get("temperature_c", 0) > 85:
                    _log_message("WARN", "High GPU temperature", gpu)
            
            # Periodic status snapshot (every ~5 ticks = ~25 seconds)
            if int(time.time()) % 25 < MONITOR_INTERVAL:
                snapshot = {
                    "ollama": ollama_status,
                    "model": model_status,
                    "system": system_stats,
                    "process": process_stats,
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
    """Returns current system status snapshot (synchronous call)."""
    return {
        "timestamp": _get_timestamp(),
        "ollama": _check_ollama_status(),
        "model": _check_ollama_model_status(),
        "system": _get_system_stats(),
        "process": _get_python_process_stats(),
    }


if __name__ == "__main__":
    # Standalone mode: run monitor until Ctrl+C
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
