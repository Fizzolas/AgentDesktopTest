# main.py
# Role: Entry point and lightweight runtime shell for the desktop agent.
# Imports from: config.py, agent_loop.py, model_adapter.py, sys (stdlib)
# Contract: main() -> None
#           print_runtime_snapshot(snapshot: dict) -> None
# NOTE: Does NOT import vision.py directly.
# NOTE: Does NOT configure the interpreter — that is agent_loop.py's responsibility.
# NOTE: This CLI shell is an interim control surface only. A cleaner GUI should
#       replace it after the core runtime refactor stabilizes.

from __future__ import annotations

import sys

from config import DEBUG, MODEL_NAME, OLLAMA_URL
import agent_loop
from model_adapter import build_default_adapter


_COMMANDS = {
    "help": "Show available commands.",
    "goal <text>": "Store a goal without running it yet.",
    "run": "Run the currently stored goal.",
    "run <text>": "Set a goal and run it immediately.",
    "status": "Show current session snapshot.",
    "queue": "Show pending queue items from the current session.",
    "notes": "Show recent session notes.",
    "last": "Show the last action and latest screen summary.",
    "clear": "Clear the currently stored goal.",
    "quit": "Exit the runtime shell.",
}


def _print_banner() -> None:
    print("=" * 68)
    print(" AgentDesktopTest Runtime Shell")
    print(f" Model   : {MODEL_NAME}")
    print(f" Backend : {OLLAMA_URL}")
    print(f" Debug   : {DEBUG}")
    print(" GUI     : Planned later after runtime core stabilizes")
    print("=" * 68)



def _print_help() -> None:
    print("[main] Available commands:")
    for name, description in _COMMANDS.items():
        print(f"  {name:<14} {description}")



def _startup_check() -> None:
    adapter = build_default_adapter()
    print("[main] Checking backend availability...")
    if not adapter.is_available():
        print(
            f"[main] ERROR: Local model backend is not reachable at {OLLAMA_URL}.\n"
            f"       Start it first (example for Ollama: ollama serve)."
        )
        sys.exit(1)
    print("[main] Backend is live.")

    print(f"[main] Loading model '{MODEL_NAME}'...")
    if not adapter.warmup(MODEL_NAME):
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



def _print_queue(snapshot: dict) -> None:
    pending = snapshot.get("pending_tasks", [])
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



def _print_notes(snapshot: dict) -> None:
    notes = snapshot.get("notes", [])
    if not notes:
        print("[main] No session notes available.")
        return

    print("[main] Recent notes")
    for note in notes[-10:]:
        print(f"  - {note}")



def _print_last(snapshot: dict) -> None:
    last_action = snapshot.get("last_action", "")
    last_screen_state = snapshot.get("last_screen_state") or {}
    print("[main] Last action")
    print(f"  {last_action or '(none)'}")
    if last_screen_state:
        print("[main] Last screen summary")
        print(f"  {last_screen_state.get('description', '(none)')}")



def _run_goal(goal: str) -> None:
    print(f"[main] Starting agent loop with goal: {goal!r}")
    print("       Press Ctrl+C at any time to stop.\n")
    try:
        agent_loop.run(goal)
    except ConnectionError as e:
        print(f"[main] Connection error: {e}")
    except Exception as e:
        print(f"[main] Unexpected error: {e}")
        if DEBUG:
            raise
    else:
        print("[main] Agent loop finished.")

    snapshot = agent_loop.get_session_snapshot()
    print_runtime_snapshot(snapshot)



def _handle_command(command: str, current_goal: str) -> str | None:
    raw = command.strip()
    if not raw:
        return current_goal

    lower = raw.lower()

    if lower in {"help", "?"}:
        _print_help()
        return current_goal

    if lower == "quit":
        return None

    if lower == "clear":
        print("[main] Stored goal cleared.")
        return ""

    if lower == "status":
        print_runtime_snapshot(agent_loop.get_session_snapshot())
        return current_goal

    if lower == "queue":
        _print_queue(agent_loop.get_session_snapshot())
        return current_goal

    if lower == "notes":
        _print_notes(agent_loop.get_session_snapshot())
        return current_goal

    if lower == "last":
        _print_last(agent_loop.get_session_snapshot())
        return current_goal

    if raw.startswith("goal "):
        updated_goal = raw[5:].strip()
        if not updated_goal:
            print("[main] Goal text cannot be empty.")
            return current_goal
        print(f"[main] Stored goal updated: {updated_goal!r}")
        return updated_goal

    if raw == "run":
        if not current_goal:
            print("[main] No stored goal. Use: goal <text> or run <text>")
            return current_goal
        _run_goal(current_goal)
        return current_goal

    if raw.startswith("run "):
        updated_goal = raw[4:].strip()
        if not updated_goal:
            print("[main] Goal text cannot be empty.")
            return current_goal
        _run_goal(updated_goal)
        return updated_goal

    print("[main] Unknown command. Type 'help' for available commands.")
    return current_goal



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

    current_goal = ""
    try:
        while True:
            prompt = "agent> " if not current_goal else f"agent[{current_goal[:24]}]> "
            try:
                command = input(prompt)
            except (KeyboardInterrupt, EOFError):
                print("\n[main] Exiting runtime shell.")
                break

            result = _handle_command(command, current_goal)
            if result is None:
                print("[main] Goodbye.")
                break
            current_goal = result
    finally:
        if agent_loop.get_session_snapshot().get("running"):
            agent_loop.stop()


if __name__ == "__main__":
    main()
