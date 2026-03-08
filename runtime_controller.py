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


@dataclass
class RuntimeController:
    adapter: BaseModelAdapter = field(default_factory=build_default_adapter)
    current_goal: str = ""
    started: bool = False
    dependency_status: dict = field(default_factory=dict)

    def get_banner_info(self) -> dict:
        settings = get_runtime_settings()
        return {
            "model": settings["MODEL_NAME"],
            "backend": settings["OLLAMA_URL"],
            "debug": settings["DEBUG"],
            "ui_mode": "gui_primary",
            "tool_provider": settings["ACTIVE_TOOL_PROVIDER"],
            "gui_note": "GUI is the primary app surface; shell is fallback only.",
        }

    def get_settings(self) -> dict:
        return get_runtime_settings()

    def get_dependency_status(self) -> dict:
        return self.dependency_status or ensure_runtime_dependencies()

    def startup(self) -> dict:
        settings = get_runtime_settings()
        self.dependency_status = ensure_runtime_dependencies()
        self.adapter = build_default_adapter()
        backend_reachable = self.adapter.is_available()
        warmup_ok = self.adapter.warmup(settings["MODEL_NAME"]) if backend_reachable else False
        self.started = backend_reachable
        return {
            "backend_reachable": backend_reachable,
            "backend_url": settings["OLLAMA_URL"],
            "model_name": settings["MODEL_NAME"],
            "warmup_ok": warmup_ok,
            "dependency_status": self.dependency_status,
            "tool_provider": self.dependency_status.get("active_provider", settings["ACTIVE_TOOL_PROVIDER"]),
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
        return self.startup()

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
        if self.dependency_status:
            snapshot["dependency_status"] = self.dependency_status
        return snapshot

    def get_dashboard_status(self) -> dict:
        status = monitor.get_dashboard_status()
        if self.dependency_status:
            status["dependency_status"] = self.dependency_status
            status["tool_provider"] = self.dependency_status.get("active_provider", self.get_settings()["ACTIVE_TOOL_PROVIDER"])
        return status

    def get_full_status(self) -> dict:
        return monitor.get_current_status()

    def get_queue_snapshot(self) -> list[dict]:
        return self.get_runtime_snapshot().get("pending_tasks", [])

    def get_recent_notes(self) -> list[str]:
        return self.get_runtime_snapshot().get("notes", [])

    def get_last_result(self) -> dict:
        snapshot = self.get_runtime_snapshot()
        return {
            "last_action": snapshot.get("last_action", ""),
            "last_screen_state": snapshot.get("last_screen_state") or {},
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
