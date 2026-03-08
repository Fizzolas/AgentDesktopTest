from __future__ import annotations

from dataclasses import dataclass, field

import agent_loop
import monitor
from bootstrap import ensure_runtime_dependencies
from config import (
    get_runtime_settings,
    update_screen_region_value as config_update_screen_region_value,
    update_setting as config_update_setting,
)
from model_adapter import BaseModelAdapter, build_default_adapter


TOOL_RELATED_SETTINGS = {
    "ACTIVE_TOOL_PROVIDER",
    "ENABLE_OPEN_INTERPRETER_TOOLS",
    "ENABLE_AGENTS2_S3_TOOLS",
    "AUTO_INSTALL_DEPENDENCIES",
    "AUTO_INSTALL_OPEN_INTERPRETER",
    "AUTO_INSTALL_AGENTS2_S3",
    "AGENTS2_S3_PIP_PACKAGE",
    "AGENTS2_S3_MODULE",
}


@dataclass
class RuntimeController:
    adapter: BaseModelAdapter = field(default_factory=build_default_adapter)
    current_goal: str = ""
    started: bool = False
    dependency_status: dict = field(default_factory=dict)

    def _tool_lists(self, dependency_status: dict | None = None) -> tuple[list[str], list[str]]:
        status = dependency_status or self.get_dependency_status()
        providers = status.get("providers", {})
        enabled_tools = [name for name, provider in providers.items() if provider.get("enabled")]
        available_tools = [name for name, provider in providers.items() if provider.get("enabled") and provider.get("installed")]
        return enabled_tools, available_tools

    def _decorate_status_payload(self, payload: dict) -> dict:
        dependency_status = self.get_dependency_status()
        settings = self.get_settings()
        enabled_tools, available_tools = self._tool_lists(dependency_status)
        payload["dependency_status"] = dependency_status
        payload["preferred_tool_provider"] = dependency_status.get("preferred_provider", settings["ACTIVE_TOOL_PROVIDER"])
        payload["tool_provider"] = dependency_status.get("active_provider", settings["ACTIVE_TOOL_PROVIDER"])
        payload["enabled_tools"] = enabled_tools
        payload["available_tools"] = available_tools
        return payload

    def get_banner_info(self) -> dict:
        settings = get_runtime_settings()
        dependency_status = self.get_dependency_status()
        enabled_tools, available_tools = self._tool_lists(dependency_status)
        return {
            "model": settings["MODEL_NAME"],
            "backend": settings["OLLAMA_URL"],
            "debug": settings["DEBUG"],
            "ui_mode": "gui_primary",
            "tool_provider": dependency_status.get("active_provider", settings["ACTIVE_TOOL_PROVIDER"]),
            "preferred_tool_provider": dependency_status.get("preferred_provider", settings["ACTIVE_TOOL_PROVIDER"]),
            "enabled_tools": enabled_tools,
            "available_tools": available_tools,
            "auto_tool_selection": settings["AUTO_TOOL_SELECTION"],
            "adaptive_vision": settings["ADAPTIVE_VISION"],
            "gui_note": "GUI is the primary app surface; shell is fallback only.",
        }

    def get_settings(self) -> dict:
        return get_runtime_settings()

    def get_dependency_status(self) -> dict:
        if not self.dependency_status:
            self.dependency_status = ensure_runtime_dependencies()
        return self.dependency_status

    def startup(self) -> dict:
        settings = get_runtime_settings()
        self.dependency_status = ensure_runtime_dependencies(force_refresh=True)
        self.adapter = build_default_adapter()
        backend_reachable = self.adapter.is_available()
        warmup_ok = self.adapter.warmup(settings["MODEL_NAME"]) if backend_reachable else False
        self.started = backend_reachable
        enabled_tools, available_tools = self._tool_lists(self.dependency_status)
        return {
            "backend_reachable": backend_reachable,
            "backend_url": settings["OLLAMA_URL"],
            "model_name": settings["MODEL_NAME"],
            "warmup_ok": warmup_ok,
            "dependency_status": self.dependency_status,
            "tool_provider": self.dependency_status.get("active_provider", settings["ACTIVE_TOOL_PROVIDER"]),
            "preferred_tool_provider": self.dependency_status.get("preferred_provider", settings["ACTIVE_TOOL_PROVIDER"]),
            "enabled_tools": enabled_tools,
            "available_tools": available_tools,
            "auto_tool_selection": settings["AUTO_TOOL_SELECTION"],
            "adaptive_vision": settings["ADAPTIVE_VISION"],
        }

    def apply_all_startup_services(self) -> dict:
        result = self.startup()
        settings = self.get_settings()
        if settings.get("START_MONITOR_ON_GUI", True):
            monitor.start_monitoring()
        else:
            monitor.stop_monitoring()
        result["monitoring"] = self.is_monitoring()
        return result

    def warmup_current_model(self) -> dict:
        settings = get_runtime_settings()
        if not self.dependency_status:
            self.dependency_status = ensure_runtime_dependencies()
        self.adapter = build_default_adapter()
        backend_reachable = self.adapter.is_available()
        warmup_ok = self.adapter.warmup(settings["MODEL_NAME"]) if backend_reachable else False
        enabled_tools, available_tools = self._tool_lists(self.dependency_status)
        return {
            "backend_reachable": backend_reachable,
            "backend_url": settings["OLLAMA_URL"],
            "model_name": settings["MODEL_NAME"],
            "warmup_ok": warmup_ok,
            "dependency_status": self.dependency_status,
            "tool_provider": self.dependency_status.get("active_provider", settings["ACTIVE_TOOL_PROVIDER"]),
            "preferred_tool_provider": self.dependency_status.get("preferred_provider", settings["ACTIVE_TOOL_PROVIDER"]),
            "enabled_tools": enabled_tools,
            "available_tools": available_tools,
            "auto_tool_selection": settings["AUTO_TOOL_SELECTION"],
            "adaptive_vision": settings["ADAPTIVE_VISION"],
        }

    def set_goal(self, goal: str) -> str:
        self.current_goal = goal.strip()
        return self.current_goal

    def get_current_goal(self) -> str:
        return self.current_goal

    def clear_goal(self) -> None:
        self.current_goal = ""

    def has_goal(self) -> bool:
        return bool(self.current_goal)

    def run_goal(self, goal: str | None = None) -> dict:
        selected_goal = (goal or self.current_goal).strip()
        if not selected_goal:
            raise ValueError("No goal is set.")
        self.current_goal = selected_goal
        agent_loop.run(selected_goal)
        return self.get_runtime_snapshot()

    def stop_runtime(self) -> None:
        if self.get_runtime_snapshot().get("running"):
            agent_loop.stop()

    def shutdown(self) -> None:
        self.stop_runtime()
        if self.is_monitoring():
            monitor.stop_monitoring()

    def get_runtime_snapshot(self) -> dict:
        snapshot = agent_loop.get_session_snapshot()
        return self._decorate_status_payload(snapshot)

    def get_dashboard_status(self) -> dict:
        status = monitor.get_dashboard_status()
        return self._decorate_status_payload(status)

    def get_full_status(self) -> dict:
        status = monitor.get_current_status()
        return self._decorate_status_payload(status)

    def get_queue_snapshot(self) -> list[dict]:
        return self.get_runtime_snapshot().get("pending_tasks", [])

    def get_recent_notes(self) -> list[str]:
        return self.get_runtime_snapshot().get("notes", [])

    def get_last_result(self) -> dict:
        snapshot = self.get_runtime_snapshot()
        return {
            "last_action": snapshot.get("last_action", ""),
            "last_screen_state": snapshot.get("last_screen_state") or {},
            "last_route": snapshot.get("last_route", ""),
            "last_vision_reason": snapshot.get("last_vision_reason", ""),
            "tool_provider": snapshot.get("tool_provider", ""),
            "preferred_tool_provider": snapshot.get("preferred_tool_provider", ""),
            "enabled_tools": snapshot.get("enabled_tools", []),
            "available_tools": snapshot.get("available_tools", []),
        }

    def start_monitoring(self) -> None:
        monitor.start_monitoring()

    def stop_monitoring(self) -> None:
        monitor.stop_monitoring()

    def is_monitoring(self) -> bool:
        return bool(getattr(monitor, "_monitoring", False))

    def update_setting(self, key: str, value) -> dict:
        updated = config_update_setting(key, value)
        self.adapter = build_default_adapter()
        if key in TOOL_RELATED_SETTINGS:
            self.dependency_status = ensure_runtime_dependencies(force_refresh=True)
        elif not self.dependency_status:
            self.dependency_status = ensure_runtime_dependencies()
        if key == "START_MONITOR_ON_GUI":
            if updated["START_MONITOR_ON_GUI"]:
                monitor.start_monitoring()
            else:
                monitor.stop_monitoring()
        return updated

    def update_screen_region_value(self, field: str, value: int) -> dict:
        updated = config_update_screen_region_value(field, value)
        self.adapter = build_default_adapter()
        return updated



def build_runtime_controller() -> RuntimeController:
    return RuntimeController()
