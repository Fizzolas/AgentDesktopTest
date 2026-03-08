from __future__ import annotations

import importlib.util
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from config import get_runtime_settings


@dataclass
class ProviderStatus:
    name: str
    enabled: bool
    module_name: str
    pip_package: str
    installed: bool
    auto_install: bool
    install_attempted: bool = False
    install_succeeded: bool = False
    error: str = ""

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "enabled": self.enabled,
            "module_name": self.module_name,
            "pip_package": self.pip_package,
            "installed": self.installed,
            "auto_install": self.auto_install,
            "install_attempted": self.install_attempted,
            "install_succeeded": self.install_succeeded,
            "error": self.error,
        }



def _module_installed(module_name: str) -> bool:
    try:
        return importlib.util.find_spec(module_name) is not None
    except Exception:
        return False



def _python_label() -> str:
    try:
        return str(Path(sys.executable).resolve())
    except Exception:
        return sys.executable



def _python_version_label() -> str:
    return f"{sys.version_info[0]}.{sys.version_info[1]}.{sys.version_info[2]}"



def _open_interpreter_supported_python() -> bool:
    major, minor = sys.version_info[:2]
    return major == 3 and 10 <= minor <= 12



def _install_package(package_name: str) -> tuple[bool, str]:
    print(f"[bootstrap] Installing {package_name} into {_python_label()} ...", flush=True)
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", package_name],
            capture_output=True,
            text=True,
            timeout=300,
        )
        if result.returncode == 0:
            print(f"[bootstrap] Installed {package_name} successfully.", flush=True)
            return True, result.stdout.strip()
        error_text = (result.stderr or result.stdout).strip()
        print(f"[bootstrap] Failed to install {package_name}: {error_text}", flush=True)
        return False, error_text
    except Exception as e:
        print(f"[bootstrap] Failed to install {package_name}: {e}", flush=True)
        return False, str(e)



def ensure_runtime_dependencies() -> dict:
    settings = get_runtime_settings()
    auto_install_all = settings["AUTO_INSTALL_DEPENDENCIES"]

    providers = {
        "open_interpreter": ProviderStatus(
            name="open_interpreter",
            enabled=settings["ENABLE_OPEN_INTERPRETER_TOOLS"],
            module_name="interpreter",
            pip_package="open-interpreter",
            installed=_module_installed("interpreter"),
            auto_install=auto_install_all and settings["AUTO_INSTALL_OPEN_INTERPRETER"],
        ),
        "agents2_s3": ProviderStatus(
            name="agents2_s3",
            enabled=settings["ENABLE_AGENTS2_S3_TOOLS"],
            module_name=settings["AGENTS2_S3_MODULE"],
            pip_package=settings["AGENTS2_S3_PIP_PACKAGE"],
            installed=_module_installed(settings["AGENTS2_S3_MODULE"]),
            auto_install=auto_install_all and settings["AUTO_INSTALL_AGENTS2_S3"],
        ),
    }

    print(f"[bootstrap] Python environment: {_python_label()}", flush=True)
    print(f"[bootstrap] Python version: {_python_version_label()}", flush=True)

    open_interpreter = providers["open_interpreter"]
    if open_interpreter.enabled and open_interpreter.auto_install and not open_interpreter.installed and not _open_interpreter_supported_python():
        open_interpreter.auto_install = False
        open_interpreter.error = (
            f"auto-install skipped: open-interpreter currently needs Python 3.10-3.12; "
            f"current runtime is {_python_version_label()}"
        )
        print(f"[bootstrap] {open_interpreter.error}", flush=True)

    agents_provider = providers["agents2_s3"]
    if agents_provider.enabled and agents_provider.auto_install and not agents_provider.installed:
        package_spec = (agents_provider.pip_package or "").strip()
        if not package_spec:
            agents_provider.auto_install = False
            agents_provider.error = (
                "auto-install skipped: AGENTS2_S3_PIP_PACKAGE is empty. "
                "Set it to a real pip package name or a git+https:// repository URL."
            )
            print(f"[bootstrap] {agents_provider.error}", flush=True)
        elif package_spec == "agents2-s3":
            agents_provider.auto_install = False
            agents_provider.error = (
                "auto-install skipped: `agents2-s3` is not a valid install target here. "
                "Use the real package name or the repo URL in git+https://... form."
            )
            print(f"[bootstrap] {agents_provider.error}", flush=True)

    for provider in providers.values():
        if provider.enabled and not provider.installed and provider.auto_install:
            provider.install_attempted = True
            provider.install_succeeded, provider.error = _install_package(provider.pip_package)
            provider.installed = provider.install_succeeded or _module_installed(provider.module_name)
            if provider.install_succeeded and not provider.error:
                provider.error = "installed during startup"

    active = settings["ACTIVE_TOOL_PROVIDER"]
    if active not in providers:
        active = "open_interpreter"

    selected = providers[active]
    fallback_applied = False
    if not selected.enabled or not selected.installed:
        fallback = providers["open_interpreter"]
        if fallback.enabled and fallback.installed:
            previous_active = active
            active = "open_interpreter"
            fallback_applied = previous_active != active
            selected = fallback

    status = {
        "requested_provider": settings["ACTIVE_TOOL_PROVIDER"],
        "active_provider": active,
        "fallback_applied": fallback_applied,
        "providers": {name: provider.to_dict() for name, provider in providers.items()},
        "ready": selected.enabled and selected.installed,
        "python_executable": _python_label(),
        "python_version": _python_version_label(),
    }
    print(
        f"[bootstrap] Dependency status: requested={status['requested_provider']} "
        f"active={status['active_provider']} ready={status['ready']}",
        flush=True,
    )
    return status
