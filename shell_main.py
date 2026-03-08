from __future__ import annotations

import json
import sys

from runtime_controller import build_runtime_controller


_COMMANDS = {
    "help": "Show available commands.",
    "goal <text>": "Store a goal without running it yet.",
    "run": "Run the currently stored goal.",
    "run <text>": "Set a goal and run it immediately.",
    "status": "Show current session snapshot.",
    "health": "Show compact dashboard health status.",
    "queue": "Show pending queue items from the current session.",
    "notes": "Show recent session notes.",
    "last": "Show the last action, route, and latest screen summary.",
    "clear": "Clear the currently stored goal.",
    "quit": "Exit the runtime shell.",
}

_controller = build_runtime_controller()



def _print_banner() -> None:
    info = _controller.get_banner_info()
    print("=" * 68)
    print(" AgentDesktopTest Shell")
    print(f" Model   : {info['model']}")
    print(f" Backend : {info['backend']}")
    print(f" Debug   : {info['debug']}")
    print(f" Tools   : provider={info['tool_provider']} | auto-select={info['auto_tool_selection']} | adaptive-vision={info['adaptive_vision']}")
    print(" GUI     : main.py launches the GUI by default")
    print("=" * 68)



def _print_help() -> None:
    print("[shell] Available commands:")
    for name, description in _COMMANDS.items():
        print(f"  {name:<14} {description}")



def _startup_check() -> None:
    print("[shell] Checking backend and providers...")
    result = _controller.startup()
    deps = result.get("dependency_status", {})
    print(f"[shell] Provider requested: {deps.get('requested_provider', 'unknown')}")
    print(f"[shell] Provider active   : {deps.get('active_provider', 'unknown')}")
    print(f"[shell] Providers ready   : {json.dumps(deps.get('providers', {}), indent=2)}")
    if not result["backend_reachable"]:
        print(
            f"[shell] ERROR: Local model backend is not reachable at {result['backend_url']}.\n"
            f"        Start it first (example for Ollama: ollama serve)."
        )
        sys.exit(1)
    print("[shell] Backend is live.")
    print(f"[shell] Loading model '{result['model_name']}'...")
    print("[shell] Model ready." if result["warmup_ok"] else "[shell] Warm-up failed; proceeding anyway.")



def print_runtime_snapshot(snapshot: dict) -> None:
    if not snapshot.get("active"):
        print("[shell] No active session.")
        return
    print("[shell] Session snapshot")
    print(f"  Session ID        : {snapshot.get('session_id', '')}")
    print(f"  Goal              : {snapshot.get('goal', '')}")
    print(f"  Status            : {snapshot.get('status', '')}")
    print(f"  Tool Provider     : {snapshot.get('tool_provider', '')}")
    print(f"  Last Route        : {snapshot.get('last_route', '')}")
    print(f"  Route Reason      : {snapshot.get('last_route_reason', '')}")
    print(f"  Vision Reason     : {snapshot.get('last_vision_reason', '')}")
    print(f"  Active Model      : {snapshot.get('active_model', '')}")
    print(f"  Pending Tasks     : {snapshot.get('pending_task_count', 0)}")
    print(f"  Completed Tasks   : {snapshot.get('completed_task_count', 0)}")
    print(f"  Failed Tasks      : {snapshot.get('failed_task_count', 0)}")



def _run_goal(goal: str) -> None:
    print(f"[shell] Starting agent loop with goal: {goal!r}")
    print("        Press Ctrl+C at any time to stop.\n")
    try:
        snapshot = _controller.run_goal(goal)
    except ValueError as e:
        print(f"[shell] {e}")
        return
    except Exception as e:
        print(f"[shell] Run error: {e}")
        return
    print("[shell] Agent loop finished.")
    print_runtime_snapshot(snapshot)



def _handle_command(command: str) -> bool:
    raw = command.strip()
    if not raw:
        return True

    lower = raw.lower()
    if lower in {"help", "?"}:
        _print_help()
        return True
    if lower == "quit":
        print("[shell] Goodbye.")
        return False
    if lower == "clear":
        _controller.clear_goal()
        print("[shell] Stored goal cleared.")
        return True
    if lower == "status":
        print_runtime_snapshot(_controller.get_runtime_snapshot())
        return True
    if lower == "health":
        print(json.dumps(_controller.get_dashboard_status(), indent=2))
        return True
    if lower == "queue":
        print(json.dumps(_controller.get_queue_snapshot(), indent=2))
        return True
    if lower == "notes":
        print(json.dumps(_controller.get_recent_notes(), indent=2))
        return True
    if lower == "last":
        print(json.dumps(_controller.get_last_result(), indent=2))
        return True
    if raw.startswith("goal "):
        goal = _controller.set_goal(raw[5:])
        print(f"[shell] Stored goal updated: {goal!r}")
        return True
    if raw == "run":
        if not _controller.has_goal():
            print("[shell] No stored goal. Use: goal <text> or run <text>")
            return True
        _run_goal(_controller.get_current_goal())
        return True
    if raw.startswith("run "):
        goal = raw[4:].strip()
        if not goal:
            print("[shell] Goal text cannot be empty.")
            return True
        _controller.set_goal(goal)
        _run_goal(goal)
        return True
    print("[shell] Unknown command. Type 'help' for available commands.")
    return True



def main() -> None:
    _print_banner()
    _startup_check()
    _print_help()
    print()
    try:
        while True:
            prompt_goal = _controller.get_current_goal()[:24]
            prompt = "agent> " if not prompt_goal else f"agent[{prompt_goal}]> "
            try:
                command = input(prompt)
            except (KeyboardInterrupt, EOFError):
                print("\n[shell] Exiting shell.")
                break
            if not _handle_command(command):
                break
    finally:
        _controller.shutdown()


if __name__ == "__main__":
    main()
