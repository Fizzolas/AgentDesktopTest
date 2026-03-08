from __future__ import annotations

from dataclasses import dataclass, field

import agent_loop, monitor
from config import get_runtime_settings, update_screen_region_value as cfg_update_region, update_setting as cfg_update
from model_adapter import BaseModelAdapter, build_default_adapter

@dataclass
class RuntimeController:
    adapter: BaseModelAdapter = field(default_factory=build_default_adapter)
    current_goal: str = ""
    started: bool = False

    def get_banner_info(self) -> dict:
        s = get_runtime_settings()
        return {"model": s["MODEL_NAME"], "backend": s["OLLAMA_URL"], "debug": s["DEBUG"], "ui_mode": "gui"}

    def get_settings(self) -> dict: return get_runtime_settings()

    def startup(self) -> dict:
        s = get_runtime_settings(); self.adapter = build_default_adapter(); live = self.adapter.is_available(); warmed = self.adapter.warmup(s["MODEL_NAME"]) if live else False; self.started = live
        return {"backend_reachable": live, "model_name": s["MODEL_NAME"], "backend_url": s["OLLAMA_URL"], "warmup_ok": warmed}

    def warmup_current_model(self) -> dict: return self.startup()
    def set_goal(self, goal: str) -> str: self.current_goal = goal.strip(); return self.current_goal
    def clear_goal(self) -> None: self.current_goal = ""
    def has_goal(self) -> bool: return bool(self.current_goal)

    def run_goal(self, goal: str | None = None) -> dict:
        g = (goal or self.current_goal).strip()
        if not g: raise ValueError("No goal is set.")
        self.current_goal = g; agent_loop.run(g); return self.get_runtime_snapshot()

    def stop_runtime(self) -> None:
        if self.get_runtime_snapshot().get("running"): agent_loop.stop()

    def get_runtime_snapshot(self) -> dict: return agent_loop.get_session_snapshot()
    def get_dashboard_status(self) -> dict: return monitor.get_dashboard_status()
    def get_full_status(self) -> dict: return monitor.get_current_status()
    def get_queue_snapshot(self) -> list[dict]: return self.get_runtime_snapshot().get("pending_tasks", [])
    def get_recent_notes(self) -> list[str]: return self.get_runtime_snapshot().get("notes", [])
    def get_last_result(self) -> dict:
        s = self.get_runtime_snapshot(); return {"last_action": s.get("last_action", ""), "last_screen_state": s.get("last_screen_state") or {}}
    def start_monitoring(self) -> None: monitor.start_monitoring()
    def stop_monitoring(self) -> None: monitor.stop_monitoring()
    def is_monitoring(self) -> bool: return bool(getattr(monitor, "_monitoring", False))

    def update_setting(self, key: str, value) -> dict:
        s = cfg_update(key, value); self.adapter = build_default_adapter()
        if key == "START_MONITOR_ON_GUI": self.start_monitoring() if s["START_MONITOR_ON_GUI"] else self.stop_monitoring()
        return s

    def update_screen_region_value(self, field: str, value: int) -> dict:
        s = cfg_update_region(field, value); self.adapter = build_default_adapter(); return s

def build_runtime_controller() -> RuntimeController: return RuntimeController()
