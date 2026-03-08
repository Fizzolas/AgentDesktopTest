# runtime_controller.py
# Role: Shared runtime control surface for CLI and future GUI layers.
# Imports from: config.py, agent_loop.py, monitor.py, model_adapter.py
# Contract: RuntimeController, build_runtime_controller()
# NOTE: This file exists to keep UI surfaces thin. The CLI shell and the future
#       polished GUI should call into this controller instead of duplicating
#       startup, goal, status, and run logic.

from __future__ import annotations

from dataclasses import dataclass, field

import agent_loop
import monitor
from config import DEBUG, MODEL_NAME, OLLAMA_URL
from model_adapter import BaseModelAdapter, build_default_adapter


@dataclass
class RuntimeController:
    adapter: BaseModelAdapter = field(default_factory=build_default_adapter)
    current_goal: str = ""
    started: bool = False

    def get_banner_info(self) -> dict:
        return {
            "model": MODEL_NAME,
            "backend": OLLAMA_URL,
            "debug": DEBUG,
            "ui_mode": "transitional_cli_shell",
            "gui_note": "Final GUI should replace this shell after runtime stabilization.",
        }

    def startup(self) -> dict:
        backend_reachable = self.adapter.is_available()
        warmed = False
        if backend_reachable:
            warmed = self.adapter.warmup(MODEL_NAME)

        self.started = backend_reachable
        return {
            "backend_reachable": backend_reachable,
            "model_name": MODEL_NAME,
            "warmup_ok": warmed,
        }

    def set_goal(self, goal: str) -> str:
        self.current_goal = goal.strip()
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

    def get_runtime_snapshot(self) -> dict:
        return agent_loop.get_session_snapshot()

    def get_dashboard_status(self) -> dict:
        return monitor.get_dashboard_status()

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



def build_runtime_controller() -> RuntimeController:
    return RuntimeController()
