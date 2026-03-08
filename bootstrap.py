from __future__ import annotations

import importlib.util
import subprocess
import sys
from dataclasses import dataclass

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



def _install_package(package_name: str) -> tuple[bool, str]:
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", package_name],
            capture_output=True,
            text=True,
            timeout=300,
        )
        if result.returncode == 0:
            return True, result.stdout.strip()
        return False, (result.stderr or result.stdout).strip()
    except Exception as e:
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
            active = "open_interpreter"
            fallback_applied = active != settings["ACTIVE_TOOL_PROVIDER"]
            selected = fallback

    return {
        "requested_provider": settings["ACTIVE_TOOL_PROVIDER"],
        "active_provider": active,
        "fallback_applied": fallback_applied,
        "providers": {name: provider.to_dict() for name, provider in providers.items()},
        "ready": selected.enabled and selected.installed,
    }
