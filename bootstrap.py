from __future__ import annotations

from copy import deepcopy
import importlib.metadata
import importlib.util
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from config import get_runtime_settings


@dataclass
class DependencyStatus:
    module_name: str
    pip_package: str
    installed: bool
    install_attempted: bool = False
    install_succeeded: bool = False
    error: str = ""

    def to_dict(self) -> dict:
        return {
            "module_name": self.module_name,
            "pip_package": self.pip_package,
            "installed": self.installed,
            "install_attempted": self.install_attempted,
            "install_succeeded": self.install_succeeded,
            "error": self.error,
        }


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


CORE_DEPENDENCIES = {
    "requests": DependencyStatus(module_name="requests", pip_package="requests>=2.32.5,<3", installed=False),
    "psutil": DependencyStatus(module_name="psutil", pip_package="psutil>=7,<8", installed=False),
    "PIL": DependencyStatus(module_name="PIL", pip_package="pillow>=12,<13", installed=False),
    "pyautogui": DependencyStatus(module_name="pyautogui", pip_package="pyautogui>=0.9.54,<1", installed=False),
    "numpy": DependencyStatus(module_name="numpy", pip_package="numpy>=2,<3", installed=False),
    "mss": DependencyStatus(module_name="mss", pip_package="mss>=9,<11", installed=False),
    "cv2": DependencyStatus(module_name="cv2", pip_package="opencv-python>=4.10,<5", installed=False),
    "easyocr": DependencyStatus(module_name="easyocr", pip_package="easyocr>=1.7,<2", installed=False),
    "pkg_resources": DependencyStatus(module_name="pkg_resources", pip_package="setuptools>=68,<81", installed=False),
}

_DEPENDENCY_STATUS_CACHE: dict[str, object] = {"key": None, "status": None}



def _module_installed(module_name: str) -> bool:
    try:
        return importlib.util.find_spec(module_name) is not None
    except Exception:
        return False



def _module_importable(module_name: str) -> tuple[bool, str]:
    try:
        __import__(module_name)
        return True, ""
    except Exception as e:
        return False, str(e)



def _dependency_available(module_name: str) -> tuple[bool, str]:
    if module_name == "pkg_resources":
        return _module_importable(module_name)
    return _module_installed(module_name), ""



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
            timeout=900,
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



def _requests_stack_needs_repair() -> bool:
    try:
        chardet_version = importlib.metadata.version("chardet")
    except importlib.metadata.PackageNotFoundError:
        return False
    try:
        major = int(chardet_version.split(".", 1)[0])
    except Exception:
        return False
    return major >= 6



def _repair_requests_stack_if_needed() -> tuple[bool, str]:
    if not _requests_stack_needs_repair():
        return True, "requests stack already compatible"
    return _install_package("chardet<6")



def _probe_provider_import(provider_name: str, module_name: str) -> tuple[bool, str]:
    if provider_name == "open_interpreter":
        code = "from interpreter import interpreter"
    else:
        code = f"import importlib; importlib.import_module({module_name!r})"

    try:
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            timeout=180,
        )
    except Exception as e:
        return False, str(e)

    if result.returncode == 0:
        return True, ""
    return False, (result.stderr or result.stdout).strip()



def _provider_ready(provider_name: str, module_name: str) -> tuple[bool, str]:
    if not _module_installed(module_name):
        return False, f"module `{module_name}` not found"
    return _probe_provider_import(provider_name, module_name)



def _dependency_cache_key(settings: dict) -> tuple:
    return (
        _python_label(),
        _python_version_label(),
        settings.get("ACTIVE_TOOL_PROVIDER"),
        settings.get("AUTO_INSTALL_DEPENDENCIES"),
        settings.get("AUTO_INSTALL_OPEN_INTERPRETER"),
        settings.get("AUTO_INSTALL_AGENTS2_S3"),
        settings.get("ENABLE_OPEN_INTERPRETER_TOOLS"),
        settings.get("ENABLE_AGENTS2_S3_TOOLS"),
        settings.get("AGENTS2_S3_PIP_PACKAGE"),
        settings.get("AGENTS2_S3_MODULE"),
    )



def ensure_core_runtime_dependencies() -> dict:
    print(f"[bootstrap] Verifying core runtime dependencies in {_python_label()} ...", flush=True)
    dependencies = {}
    for name, status in CORE_DEPENDENCIES.items():
        installed, error = _dependency_available(status.module_name)
        dependencies[name] = DependencyStatus(
            module_name=status.module_name,
            pip_package=status.pip_package,
            installed=installed,
            error=error,
        )

    for dependency in dependencies.values():
        if dependency.installed:
            continue
        dependency.install_attempted = True
        dependency.install_succeeded, dependency.error = _install_package(dependency.pip_package)
        dependency.installed, availability_error = _dependency_available(dependency.module_name)
        if not dependency.installed and availability_error:
            dependency.error = availability_error
        elif dependency.install_succeeded and not dependency.error:
            dependency.error = "installed during startup"

    repair_ok, repair_message = _repair_requests_stack_if_needed()
    ready = all(dep.installed for dep in dependencies.values()) and repair_ok
    print(f"[bootstrap] Core dependency status: ready={ready}", flush=True)
    return {
        "ready": ready,
        "python_executable": _python_label(),
        "python_version": _python_version_label(),
        "requests_stack_repair_ok": repair_ok,
        "requests_stack_repair_message": repair_message,
        "dependencies": {name: dependency.to_dict() for name, dependency in dependencies.items()},
    }



def ensure_runtime_dependencies(force_refresh: bool = False) -> dict:
    settings = get_runtime_settings()
    cache_key = _dependency_cache_key(settings)
    cached_status = _DEPENDENCY_STATUS_CACHE.get("status")
    if not force_refresh and _DEPENDENCY_STATUS_CACHE.get("key") == cache_key and isinstance(cached_status, dict):
        return deepcopy(cached_status)

    auto_install_all = settings["AUTO_INSTALL_DEPENDENCIES"]

    open_interpreter_installed, open_interpreter_error = _provider_ready("open_interpreter", "interpreter")
    agents_installed, agents_error = _provider_ready("agents2_s3", settings["AGENTS2_S3_MODULE"])

    providers = {
        "open_interpreter": ProviderStatus(
            name="open_interpreter",
            enabled=settings["ENABLE_OPEN_INTERPRETER_TOOLS"],
            module_name="interpreter",
            pip_package="open-interpreter",
            installed=open_interpreter_installed,
            auto_install=auto_install_all and settings["AUTO_INSTALL_OPEN_INTERPRETER"],
            error=open_interpreter_error,
        ),
        "agents2_s3": ProviderStatus(
            name="agents2_s3",
            enabled=settings["ENABLE_AGENTS2_S3_TOOLS"],
            module_name=settings["AGENTS2_S3_MODULE"],
            pip_package=settings["AGENTS2_S3_PIP_PACKAGE"],
            installed=agents_installed,
            auto_install=auto_install_all and settings["AUTO_INSTALL_AGENTS2_S3"],
            error=agents_error,
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
            provider.installed, import_error = _provider_ready(provider.name, provider.module_name)
            if not provider.installed and import_error:
                provider.error = import_error
            elif provider.install_succeeded and not provider.error:
                provider.error = "installed during startup"

    repair_ok, repair_message = _repair_requests_stack_if_needed()

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

    enabled_tools = [name for name, provider in providers.items() if provider.enabled]
    available_tools = [name for name, provider in providers.items() if provider.enabled and provider.installed]

    status = {
        "requested_provider": settings["ACTIVE_TOOL_PROVIDER"],
        "preferred_provider": settings["ACTIVE_TOOL_PROVIDER"],
        "active_provider": active,
        "fallback_applied": fallback_applied,
        "providers": {name: provider.to_dict() for name, provider in providers.items()},
        "enabled_tools": enabled_tools,
        "available_tools": available_tools,
        "ready": selected.enabled and selected.installed and repair_ok,
        "python_executable": _python_label(),
        "python_version": _python_version_label(),
        "requests_stack_repair_ok": repair_ok,
        "requests_stack_repair_message": repair_message,
    }
    print(
        f"[bootstrap] Dependency status: requested={status['requested_provider']} "
        f"active={status['active_provider']} ready={status['ready']}",
        flush=True,
    )

    _DEPENDENCY_STATUS_CACHE["key"] = cache_key
    _DEPENDENCY_STATUS_CACHE["status"] = deepcopy(status)
    return deepcopy(status)
