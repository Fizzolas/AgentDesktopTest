# main.py
# Role: Entry point and lightweight runtime shell for the desktop agent.
# Imports from: config.py, runtime_controller.py, sys (stdlib)
# Contract: main() -> None
#           print_runtime_snapshot(snapshot: dict) -> None
# NOTE: This CLI shell is an interim control surface only. A cleaner GUI should
#       replace it after the core runtime refactor stabilizes.

from __future__ import annotations

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
    "last": "Show the last action and latest screen summary.",
    "clear": "Clear the currently stored goal.",
    "quit": "Exit the runtime shell.",
}

_controller = build_runtime_controller()



def _print_banner() -> None:
    info = _controller.get_banner_info()
    print("=" * 68)
    print(" AgentDesktopTest Runtime Shell")
    print(f" Model   : {info['model']}")
    print(f" Backend : {info['backend']}")
    print(f" Debug   : {info['debug']}")
    print(" GUI     : Planned later after runtime core stabilizes")
    print("=" * 68)



def _print_help() -> None:
    print("[main] Available commands:")
    for name, description in _COMMANDS.items():
        print(f"  {name:<14} {description}")



def _startup_check() -> None:
    print("[main] Checking backend availability...")
    result = _controller.startup()
    if not result["backend_reachable"]:
        banner = _controller.get_banner_info()
        print(
            f"[main] ERROR: Local model backend is not reachable at {banner['backend']}.\n"
            f"       Start it first (example for Ollama: ollama serve)."
        )
        sys.exit(1)
    print("[main] Backend is live.")

    print(f"[main] Loading model '{result['model_name']}'...")
    if not result["warmup_ok"]:
        print(
            "[main] WARNING: Model warm-up failed. "
            "Proceeding anyway — first query may be slow."
        )
    else:
        print("[main] Model ready.")



def print_runtime_snapshot(snapshot: dict) -> None:
    if not snapshot.get("active"):
        print("[main] No active session.")
        return

    print("[main] Session snapshot")
    print(f"  Session ID        : {snapshot.get('session_id', '')}")
    print(f"  Goal              : {snapshot.get('goal', '')}")
    print(f"  Status            : {snapshot.get('status', '')}")
    print(f"  Active Model      : {snapshot.get('active_model', '')}")
    print(f"  Planner Model     : {snapshot.get('planner_model', '')}")
    print(f"  Executor Model    : {snapshot.get('executor_model', '')}")
    print(f"  Pending Tasks     : {snapshot.get('pending_task_count', 0)}")
    print(f"  Completed Tasks   : {snapshot.get('completed_task_count', 0)}")
    print(f"  Failed Tasks      : {snapshot.get('failed_task_count', 0)}")



def _print_health() -> None:
    status = _controller.get_dashboard_status()
    print("[main] Health status")
    print(f"  Summary           : {status.get('summary', '')}")
    print(f"  Backend Reachable : {status.get('backend_reachable', False)}")
    print(f"  Model Loaded      : {status.get('model_loaded', False)}")
    print(f"  Runtime Running   : {status.get('runtime_running', False)}")
    print(f"  Runtime Status    : {status.get('runtime_status', '')}")
    print(f"  Pending Tasks     : {status.get('pending_task_count', 0)}")
    print(f"  Completed Tasks   : {status.get('completed_task_count', 0)}")
    print(f"  Failed Tasks      : {status.get('failed_task_count', 0)}")
    print(f"  CPU %             : {status.get('cpu_percent')}")
    print(f"  RAM %             : {status.get('ram_percent')}")
    print(f"  GPU Util %        : {status.get('gpu_utilization_percent')}")
    print(f"  GPU Temp C        : {status.get('gpu_temperature_c')}")
    flags = status.get("health_flags", [])
    if flags:
        print(f"  Flags             : {', '.join(flags)}")



def _print_queue() -> None:
    pending = _controller.get_queue_snapshot()
    if not pending:
        print("[main] No pending queue items.")
        return

    print("[main] Pending queue")
    for task in pending:
        print(
            f"  - {task.get('kind', 'unknown')} | "
            f"priority={task.get('priority', '')} | "
            f"status={task.get('status', '')} | "
            f"{task.get('title', '')}"
        )



def _print_notes() -> None:
    notes = _controller.get_recent_notes()
    if not notes:
        print("[main] No session notes available.")
        return

    print("[main] Recent notes")
    for note in notes[-10:]:
        print(f"  - {note}")



def _print_last() -> None:
    result = _controller.get_last_result()
    print("[main] Last action")
    print(f"  {result.get('last_action') or '(none)'}")
    last_screen_state = result.get("last_screen_state") or {}
    if last_screen_state:
        print("[main] Last screen summary")
        print(f"  {last_screen_state.get('description', '(none)')}")



def _run_goal(goal: str) -> None:
    print(f"[main] Starting agent loop with goal: {goal!r}")
    print("       Press Ctrl+C at any time to stop.\n")
    try:
        snapshot = _controller.run_goal(goal)
    except ValueError as e:
        print(f"[main] {e}")
        return
    except ConnectionError as e:
        print(f"[main] Connection error: {e}")
        return
    except Exception as e:
        print(f"[main] Unexpected error: {e}")
        raise
    else:
        print("[main] Agent loop finished.")
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
        print("[main] Goodbye.")
        return False

    if lower == "clear":
        _controller.clear_goal()
        print("[main] Stored goal cleared.")
        return True

    if lower == "status":
        print_runtime_snapshot(_controller.get_runtime_snapshot())
        return True

    if lower == "health":
        _print_health()
        return True

    if lower == "queue":
        _print_queue()
        return True

    if lower == "notes":
        _print_notes()
        return True

    if lower == "last":
        _print_last()
        return True

    if raw.startswith("goal "):
        updated_goal = _controller.set_goal(raw[5:])
        if not updated_goal:
            print("[main] Goal text cannot be empty.")
            return True
        print(f"[main] Stored goal updated: {updated_goal!r}")
        return True

    if raw == "run":
        if not _controller.has_goal():
            print("[main] No stored goal. Use: goal <text> or run <text>")
            return True
        _run_goal(_controller.current_goal)
        return True

    if raw.startswith("run "):
        goal = raw[4:].strip()
        if not goal:
            print("[main] Goal text cannot be empty.")
            return True
        _controller.set_goal(goal)
        _run_goal(goal)
        return True

    print("[main] Unknown command. Type 'help' for available commands.")
    return True



def main() -> None:
    """
    Entry point for the desktop agent runtime shell.
    Provides a cleaner control layer than the original one-shot CLI while the
    full GUI remains deferred until the core runtime migration is complete.
    """
    _print_banner()
    _startup_check()
    _print_help()
    print()

    try:
        while True:
            prompt_goal = _controller.current_goal[:24]
            prompt = "agent> " if not prompt_goal else f"agent[{prompt_goal}]> "
            try:
                command = input(prompt)
            except (KeyboardInterrupt, EOFError):
                print("\n[main] Exiting runtime shell.")
                break

            if not _handle_command(command):
                break
    finally:
        _controller.stop_runtime()


if __name__ == "__main__":
    main()
