from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import traceback

PROJECT_ROOT = Path(__file__).resolve().parent
VENV_DIR = PROJECT_ROOT / ".venv"
BOOTSTRAP_STATE_FILE = VENV_DIR / ".agentdesktop_bootstrap.json"
REQUIREMENTS_FILE = PROJECT_ROOT / "requirements.txt"
REQUIRED_PYTHON = (3, 11)
REQUIRED_PYTHON_TEXT = f"{REQUIRED_PYTHON[0]}.{REQUIRED_PYTHON[1]}"



def _print(message: str) -> None:
    print(message, flush=True)



def _pause_before_exit(message: str = "") -> None:
    if message:
        _print(message)
    if sys.stdin is not None and sys.stdin.isatty():
        try:
            input("[main] Press Enter to close this window...")
        except Exception:
            pass



def _venv_python_path() -> Path:
    if os.name == "nt":
        return VENV_DIR / "Scripts" / "python.exe"
    return VENV_DIR / "bin" / "python"



def _current_python_is_required() -> bool:
    return tuple(sys.version_info[:2]) == REQUIRED_PYTHON



def _probe_python_command(command: list[str]) -> tuple[bool, str, str]:
    try:
        result = subprocess.run(
            command + ["-c", "import sys; print(f'{sys.version_info[0]}.{sys.version_info[1]}'); print(sys.executable)"],
            capture_output=True,
            text=True,
            timeout=20,
        )
        if result.returncode != 0:
            return False, "", (result.stderr or result.stdout).strip()
        lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
        if len(lines) < 2:
            return False, "", result.stdout.strip()
        version = lines[0]
        executable = lines[1]
        return True, version, executable
    except Exception as e:
        return False, "", str(e)



def _candidate_python_commands() -> list[list[str]]:
    candidates: list[list[str]] = []
    if sys.executable:
        candidates.append([sys.executable])
    if os.name == "nt":
        candidates.append(["py", f"-{REQUIRED_PYTHON_TEXT}"])
    candidates.append([f"python{REQUIRED_PYTHON_TEXT}"])
    candidates.append(["python"])

    unique: list[list[str]] = []
    seen: set[tuple[str, ...]] = set()
    for candidate in candidates:
        key = tuple(candidate)
        if key not in seen:
            seen.add(key)
            unique.append(candidate)
    return unique



def _select_python_command() -> list[str]:
    diagnostics: list[str] = []
    for candidate in _candidate_python_commands():
        ok, version, executable_or_error = _probe_python_command(candidate)
        if ok and version == REQUIRED_PYTHON_TEXT:
            _print(f"[main] Using Python {REQUIRED_PYTHON_TEXT} interpreter: {executable_or_error}")
            return candidate
        label = " ".join(candidate)
        if ok:
            diagnostics.append(f"{label} -> Python {version}")
        else:
            diagnostics.append(f"{label} -> {executable_or_error}")

    joined = " | ".join(diagnostics) if diagnostics else "no interpreter probes succeeded"
    raise RuntimeError(
        f"Python {REQUIRED_PYTHON_TEXT} is required but was not found on this system. "
        f"Install Python {REQUIRED_PYTHON_TEXT} and re-run main.py. Probe results: {joined}"
    )



def _venv_uses_required_python() -> bool:
    venv_python = _venv_python_path()
    if not venv_python.exists():
        return False
    ok, version, _ = _probe_python_command([str(venv_python)])
    return ok and version == REQUIRED_PYTHON_TEXT



def _running_in_project_venv() -> bool:
    try:
        return Path(sys.executable).resolve() == _venv_python_path().resolve() and _current_python_is_required()
    except Exception:
        return False



def _run_command(command: list[str], label: str) -> None:
    _print(f"[main] {label} ...")
    result = subprocess.run(
        command,
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
    )
    if result.stdout.strip():
        _print(result.stdout.strip())
    if result.stderr.strip():
        _print(result.stderr.strip())
    if result.returncode != 0:
        raise RuntimeError(f"{label} failed with exit code {result.returncode}")



def _remove_existing_venv() -> None:
    if not VENV_DIR.exists():
        return
    _print(f"[main] Removing existing virtual environment at {VENV_DIR} ...")
    shutil.rmtree(VENV_DIR)



def _create_venv_if_missing() -> None:
    selected_python = _select_python_command()
    venv_python = _venv_python_path()

    if venv_python.exists() and _venv_uses_required_python():
        return

    if venv_python.exists() and not _venv_uses_required_python():
        _print(f"[main] Existing virtual environment is not using Python {REQUIRED_PYTHON_TEXT}; rebuilding it.")
        _remove_existing_venv()
    elif not venv_python.exists() and VENV_DIR.exists():
        _remove_existing_venv()

    _run_command(selected_python + ["-m", "venv", str(VENV_DIR)], f"Creating project virtual environment with Python {REQUIRED_PYTHON_TEXT}")
    if not venv_python.exists():
        raise RuntimeError(f"Virtual environment creation finished but python was not found at {venv_python}")
    if not _venv_uses_required_python():
        raise RuntimeError(f"The created virtual environment is not using Python {REQUIRED_PYTHON_TEXT}")



def _load_bootstrap_state() -> dict:
    if not BOOTSTRAP_STATE_FILE.exists():
        return {}
    try:
        return json.loads(BOOTSTRAP_STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}



def _save_bootstrap_state(requirements_mtime: float) -> None:
    VENV_DIR.mkdir(parents=True, exist_ok=True)
    BOOTSTRAP_STATE_FILE.write_text(
        json.dumps(
            {
                "requirements_mtime": requirements_mtime,
                "python": str(Path(sys.executable).resolve()),
                "python_version": f"{sys.version_info[0]}.{sys.version_info[1]}",
            },
            indent=2,
        ),
        encoding="utf-8",
    )



def _ensure_venv_packages() -> None:
    requirements_mtime = REQUIREMENTS_FILE.stat().st_mtime if REQUIREMENTS_FILE.exists() else 0.0
    state = _load_bootstrap_state()
    current_python = str(Path(sys.executable).resolve())

    if (
        state.get("requirements_mtime") == requirements_mtime
        and state.get("python") == current_python
        and state.get("python_version") == REQUIRED_PYTHON_TEXT
    ):
        _print("[main] Virtual environment packages already prepared.")
        return

    _run_command([sys.executable, "-m", "ensurepip", "--upgrade"], "Ensuring pip inside project virtual environment")
    _run_command([sys.executable, "-m", "pip", "install", "--upgrade", "pip", "setuptools", "wheel"], "Updating base packaging tools")

    if REQUIREMENTS_FILE.exists():
        _run_command([sys.executable, "-m", "pip", "install", "-r", str(REQUIREMENTS_FILE)], "Installing project requirements into the virtual environment")
    else:
        _print("[main] No requirements.txt found; skipping base dependency install.")

    _save_bootstrap_state(requirements_mtime=requirements_mtime)



def _relaunch_in_project_venv() -> None:
    if _running_in_project_venv():
        return

    _create_venv_if_missing()
    venv_python = _venv_python_path()
    _print(f"[main] Relaunching with project virtual environment: {venv_python}")
    env = os.environ.copy()
    env["VIRTUAL_ENV"] = str(VENV_DIR)
    result = subprocess.run([str(venv_python), str(PROJECT_ROOT / "main.py"), *sys.argv[1:]], cwd=str(PROJECT_ROOT), env=env)
    if result.returncode != 0:
        _pause_before_exit(f"[main] Project virtual environment run failed with exit code {result.returncode}.")
    raise SystemExit(result.returncode)



def _launch_gui_or_fallback() -> None:
    try:
        from gui_app import main as gui_main
    except Exception as e:
        _print(f"[main] GUI import failed: {e}")
        from shell_main import main as shell_main
        _print("[main] Falling back to shell mode.")
        shell_main()
        return

    try:
        _print("[main] Launching GUI ...")
        gui_main()
    except Exception as e:
        _print(f"[main] GUI launch failed: {e}")
        from shell_main import main as shell_main
        _print("[main] Falling back to shell mode.")
        shell_main()



def main() -> None:
    _print("[main] Starting AgentDesktopTest ...")
    _print(f"[main] Required Python baseline: {REQUIRED_PYTHON_TEXT}")
    _print(f"[main] Current interpreter: {sys.executable} ({sys.version.split()[0]})")
    _relaunch_in_project_venv()
    _ensure_venv_packages()

    from bootstrap import ensure_core_runtime_dependencies, ensure_runtime_dependencies

    _print("[main] Verifying core runtime dependencies inside the project virtual environment ...")
    core_status = ensure_core_runtime_dependencies()
    _print(f"[main] Core dependency verification complete. ready={core_status.get('ready')}")

    _print("[main] Running dependency bootstrap inside the project virtual environment ...")
    dependency_status = ensure_runtime_dependencies()
    _print(
        f"[main] Dependency bootstrap complete. requested={dependency_status.get('requested_provider')} "
        f"active={dependency_status.get('active_provider')} ready={dependency_status.get('ready')}"
    )
    _launch_gui_or_fallback()


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:
        _print(f"[main] Startup failed: {e}")
        _print(traceback.format_exc())
        _pause_before_exit()
        raise
