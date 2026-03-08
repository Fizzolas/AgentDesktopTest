from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import venv

PROJECT_ROOT = Path(__file__).resolve().parent
VENV_DIR = PROJECT_ROOT / ".venv"
BOOTSTRAP_STATE_FILE = VENV_DIR / ".agentdesktop_bootstrap.json"
REQUIREMENTS_FILE = PROJECT_ROOT / "requirements.txt"



def _print(message: str) -> None:
    print(message, flush=True)



def _venv_python_path() -> Path:
    if os.name == "nt":
        return VENV_DIR / "Scripts" / "python.exe"
    return VENV_DIR / "bin" / "python"



def _running_in_project_venv() -> bool:
    try:
        return Path(sys.executable).resolve() == _venv_python_path().resolve()
    except Exception:
        return False



def _create_venv_if_missing() -> None:
    venv_python = _venv_python_path()
    if venv_python.exists():
        return
    _print(f"[main] Creating project virtual environment at {VENV_DIR} ...")
    builder = venv.EnvBuilder(with_pip=True, clear=False, symlinks=False, upgrade=False)
    builder.create(VENV_DIR)
    if not venv_python.exists():
        raise RuntimeError(f"Virtual environment creation finished but python was not found at {venv_python}")



def _run_command(command: list[str], label: str) -> None:
    _print(f"[main] {label} ...")
    result = subprocess.run(command, cwd=str(PROJECT_ROOT))
    if result.returncode != 0:
        raise RuntimeError(f"{label} failed with exit code {result.returncode}")



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
            },
            indent=2,
        ),
        encoding="utf-8",
    )



def _ensure_venv_packages() -> None:
    requirements_mtime = REQUIREMENTS_FILE.stat().st_mtime if REQUIREMENTS_FILE.exists() else 0.0
    state = _load_bootstrap_state()
    current_python = str(Path(sys.executable).resolve())

    if state.get("requirements_mtime") == requirements_mtime and state.get("python") == current_python:
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
    _relaunch_in_project_venv()
    _ensure_venv_packages()

    from bootstrap import ensure_runtime_dependencies

    _print("[main] Running dependency bootstrap inside the project virtual environment ...")
    dependency_status = ensure_runtime_dependencies()
    _print(
        f"[main] Dependency bootstrap complete. requested={dependency_status.get('requested_provider')} "
        f"active={dependency_status.get('active_provider')} ready={dependency_status.get('ready')}"
    )
    _launch_gui_or_fallback()


if __name__ == "__main__":
    main()
