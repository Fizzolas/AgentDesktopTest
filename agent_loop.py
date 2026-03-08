# agent_loop.py
# Role: Core autonomous goal loop. Orchestrates all components.
# Imports from: config.py, vision.py, model_adapter.py, runtime_models.py, open-interpreter
# Contract: run(goal: str) -> None
#           step(goal: str, screen_state: dict | ScreenState) -> str
#           stop() -> None
#           get_session_snapshot() -> dict
# NOTE: This is the ONLY file that calls vision.py directly.
# NOTE: interpreter object is instantiated ONCE here and reused for the session.
# NOTE: Legacy Open Interpreter execution remains active while typed session state
#       and queue scaffolding are introduced underneath it.

from __future__ import annotations

import os
import time
from typing import Any

from interpreter import interpreter

from config import (
    MODEL_NAME,
    OLLAMA_URL,
    LOOP_DELAY,
    DEBUG,
    BLOCK_CPU_COMPUTE,
    OLLAMA_NUM_GPU,
)
from model_adapter import build_default_adapter
from runtime_models import AgentTask, ScreenState, SessionState, TaskKind, TaskPriority, create_task
from vision import get_screen_state

# =============================================================================
# Block CPU from performing ANY GPU compute operations
# =============================================================================
if BLOCK_CPU_COMPUTE:
    os.environ["CUDA_LAUNCH_BLOCKING"] = "1"
    os.environ["CUDA_DEVICE_ORDER"] = "PCI_BUS_ID"
    os.environ["CUDA_VISIBLE_DEVICES"] = "0"
    os.environ["OMP_NUM_THREADS"] = "1"
    os.environ["MKL_NUM_THREADS"] = "1"
    if DEBUG:
        print("[agent_loop] CPU compute blocked. GPU-only mode enforced.")

# =============================================================================
# Open Interpreter — configured once at module load
# =============================================================================
interpreter.llm.model = f"ollama/{MODEL_NAME}"
interpreter.llm.api_base = OLLAMA_URL
interpreter.auto_run = True
interpreter.verbose = DEBUG
interpreter.offline = True
interpreter.llm.num_gpu = OLLAMA_NUM_GPU

if DEBUG:
    print(f"[agent_loop] Ollama config: num_gpu={OLLAMA_NUM_GPU} (RAM offload enabled if needed)")

# =============================================================================
# Runtime baseline state
# =============================================================================
_model_adapter = build_default_adapter()
_running = False
_active_session: SessionState | None = None
_last_action: str = ""

# =============================================================================
# System prompt injected into every OI session
# =============================================================================
_SYSTEM_PROMPT = """
You are an autonomous desktop agent running on a Windows 10 machine.
You observe the current screen state and take actions to accomplish the user's goal.
You have access to Python and shell execution via Open Interpreter.
Always reason step by step. After each action, wait for screen feedback before proceeding.
When the goal is fully accomplished, respond with exactly: GOAL_COMPLETE
""".strip()


# =============================================================================
# Internal helpers — typed session baseline + queue scaffolding
# =============================================================================
def _normalize_screen_state(screen_state: dict | ScreenState | None) -> ScreenState:
    if isinstance(screen_state, ScreenState):
        return screen_state
    return ScreenState.from_legacy(screen_state or {})


def _make_session(goal: str) -> SessionState:
    session = SessionState(
        goal=goal,
        active_model=MODEL_NAME,
        planner_model=MODEL_NAME,
        executor_model=MODEL_NAME,
        status="starting",
    )
    session.add_note("Session created.")
    _seed_initial_queue(session)
    return session


def _seed_initial_queue(session: SessionState) -> None:
    if session.task_queue or session.completed_tasks:
        return
    session.enqueue(
        create_task(
            title="Observe desktop state",
            instructions=(
                "Inspect the current desktop screen and summarize the most relevant UI state "
                "for the active goal before taking further action."
            ),
            kind=TaskKind.OBSERVE,
            priority=TaskPriority.CRITICAL,
        )
    )
    session.enqueue(
        create_task(
            title="Plan next action",
            instructions=(
                "Decide the best next action for the user's goal using available local tools, "
                "screen information, and prior actions."
            ),
            kind=TaskKind.PLAN,
            priority=TaskPriority.HIGH,
        )
    )


def _ensure_follow_up_tasks(session: SessionState, completed_task: AgentTask | None = None) -> None:
    pending_kinds = {task.kind for task in session.task_queue}

    if completed_task is None and not session.task_queue:
        session.enqueue(
            create_task(
                title="Continue goal progress",
                instructions="Continue moving the goal forward using the current screen state.",
                kind=TaskKind.THINK,
                priority=TaskPriority.NORMAL,
            )
        )
        return

    if completed_task is None:
        return

    if completed_task.kind in (TaskKind.OBSERVE, TaskKind.PLAN) and TaskKind.THINK not in pending_kinds:
        session.enqueue(
            create_task(
                title="Take next best action",
                instructions=(
                    "Take the single best next action that advances the goal, then wait for "
                    "the next screen feedback cycle."
                ),
                kind=TaskKind.THINK,
                priority=TaskPriority.HIGH,
            )
        )

    elif completed_task.kind == TaskKind.THINK and TaskKind.VERIFY not in pending_kinds:
        session.enqueue(
            create_task(
                title="Verify outcome",
                instructions=(
                    "Inspect the latest visible state and verify whether the last action made "
                    "progress toward the goal."
                ),
                kind=TaskKind.VERIFY,
                priority=TaskPriority.HIGH,
            )
        )

    elif completed_task.kind == TaskKind.VERIFY and TaskKind.THINK not in pending_kinds:
        session.enqueue(
            create_task(
                title="Continue goal progress",
                instructions="Choose the next best action based on the verified screen feedback.",
                kind=TaskKind.THINK,
                priority=TaskPriority.NORMAL,
            )
        )


def _next_task(session: SessionState) -> AgentTask:
    task = session.pop_next_task()
    if task is None:
        _ensure_follow_up_tasks(session, completed_task=None)
        task = session.pop_next_task()
    if task is None:
        task = create_task(
            title="Fallback reasoning step",
            instructions="Reason about the next best action for the current goal.",
            kind=TaskKind.THINK,
            priority=TaskPriority.NORMAL,
        )
    task.mark_running()
    return task


def _queue_preview(session: SessionState, limit: int = 5) -> str:
    if not session.task_queue:
        return "(empty)"
    lines = []
    for task in session.task_queue[:limit]:
        lines.append(f"- [{task.kind.value}|{task.priority.name}] {task.title}")
    return "\n".join(lines)


def _build_prompt(goal: str, session: SessionState, task: AgentTask, screen_state: ScreenState) -> str:
    prompt_parts = [
        f"GOAL: {goal}",
        f"SESSION_ID: {session.session_id}",
        f"ACTIVE MODEL: {session.active_model}",
        f"CURRENT TASK: {task.title}",
        f"TASK KIND: {task.kind.value}",
        f"TASK INSTRUCTIONS: {task.instructions}",
        f"CURRENT SCREEN: {screen_state.description or 'No screen data available.'}",
    ]

    visible_text = screen_state.text_preview(500)
    if visible_text:
        prompt_parts.append(f"VISIBLE TEXT: {visible_text}")

    if _last_action:
        prompt_parts.append(f"LAST ACTION SUMMARY: {_last_action[:600]}")

    prompt_parts.append(f"COMPLETED TASKS: {len(session.completed_tasks)}")
    prompt_parts.append("PENDING TASK QUEUE:")
    prompt_parts.append(_queue_preview(session))
    prompt_parts.append(
        "If you execute an action, make it the best single next step. "
        "After the action, wait for the next screen feedback cycle."
    )

    return "\n\n".join(prompt_parts)


def _extract_action(response_messages: list[dict[str, Any]]) -> str:
    for msg in reversed(response_messages):
        if msg.get("role") == "assistant" and msg.get("content"):
            return str(msg["content"]).strip()
    return ""


def _record_completed_task(session: SessionState, task: AgentTask, action: str) -> None:
    note = action[:800] if action else "No assistant action content returned."
    task.add_note(note)
    session.record_completed(task)
    session.metadata["last_completed_task_id"] = task.task_id
    if action:
        session.metadata["last_action"] = action[:2000]


def _task_to_dict(task: AgentTask) -> dict[str, Any]:
    return {
        "task_id": task.task_id,
        "title": task.title,
        "kind": task.kind.value,
        "priority": int(task.priority),
        "status": task.status.value,
        "attempts": task.attempts,
        "max_attempts": task.max_attempts,
        "assigned_model": task.assigned_model,
        "assigned_tool": task.assigned_tool,
        "notes": list(task.notes),
        "context": dict(task.context),
    }


# =============================================================================
# Public API
# =============================================================================
def step(goal: str, screen_state: dict | ScreenState) -> str:
    """
    Runs a single agent tick using the new typed session baseline while preserving
    the legacy Open Interpreter execution path.
    """
    global _active_session, _last_action

    session = _active_session if _active_session and _active_session.goal == goal else _make_session(goal)
    _active_session = session
    session.status = "running"

    runtime_screen_state = _normalize_screen_state(screen_state)
    session.last_screen_state = runtime_screen_state

    task = _next_task(session)
    prompt = _build_prompt(goal, session, task, runtime_screen_state)

    if DEBUG:
        print(f"[agent_loop] step() task: {task.kind.value} :: {task.title}")
        print(f"[agent_loop] step() prompt:\n{prompt}")

    response_messages = interpreter.chat(prompt, display=DEBUG, stream=False)
    action = _extract_action(response_messages)
    _last_action = action

    _record_completed_task(session, task, action)
    if "GOAL_COMPLETE" in action:
        session.status = "complete"
        session.add_note("Goal completion signal received.")
    else:
        _ensure_follow_up_tasks(session, completed_task=task)

    if DEBUG:
        print(f"[agent_loop] step() action: {action}")
        print(f"[agent_loop] step() pending queue size: {len(session.task_queue)}")

    return action


def run(goal: str) -> None:
    """
    Main entry point for the agent loop.
    Accepts a plain-English goal string.
    Runs continuously until GOAL_COMPLETE is returned or user interrupts (Ctrl+C).
    """
    global _running, _active_session, _last_action

    if not _model_adapter.is_available():
        raise ConnectionError("Ollama is not reachable. Start Ollama before calling agent_loop.run().")

    interpreter.messages = []
    interpreter.system_message = _SYSTEM_PROMPT

    _active_session = _make_session(goal)
    _last_action = ""
    _running = True
    tick = 0

    print(f"[agent_loop] Starting. Goal: {goal}")

    try:
        while _running:
            tick += 1
            if DEBUG:
                print(f"[agent_loop] Tick {tick}")

            screen_state = get_screen_state()
            action = step(goal, screen_state)

            if "GOAL_COMPLETE" in action:
                print(f"[agent_loop] Goal complete after {tick} tick(s).")
                break

            time.sleep(LOOP_DELAY)

    except KeyboardInterrupt:
        print("[agent_loop] Interrupted by user.")
        if _active_session:
            _active_session.status = "interrupted"
            _active_session.add_note("Interrupted by user.")
    finally:
        _running = False
        if _active_session and _active_session.status != "complete":
            _active_session.status = "stopped"
        if DEBUG:
            print(f"[agent_loop] Loop exited after {tick} tick(s).")


def get_session_snapshot() -> dict:
    """
    Returns a lightweight snapshot of the current typed session state.
    This is the first public inspection hook for future UI and task-queue tooling.
    """
    session = _active_session
    if session is None:
        return {
            "active": False,
            "running": _running,
            "last_action": _last_action,
        }

    return {
        "active": True,
        "running": _running,
        "session_id": session.session_id,
        "goal": session.goal,
        "status": session.status,
        "active_model": session.active_model,
        "planner_model": session.planner_model,
        "executor_model": session.executor_model,
        "created_at": session.created_at,
        "completed_task_count": len(session.completed_tasks),
        "failed_task_count": len(session.failed_tasks),
        "pending_task_count": len(session.task_queue),
        "last_action": _last_action,
        "last_screen_state": session.last_screen_state.to_legacy() if session.last_screen_state else None,
        "pending_tasks": [_task_to_dict(task) for task in session.task_queue],
        "completed_tasks": [_task_to_dict(task) for task in session.completed_tasks[-10:]],
        "notes": list(session.notes[-20:]),
        "metadata": dict(session.metadata),
    }


def stop() -> None:
    """
    Gracefully stops the agent loop and cleans up the interpreter session.
    Sets _running to False so the run() while loop exits on next iteration.
    Resets interpreter message history to free memory.
    """
    global _running
    _running = False
    interpreter.messages = []
    if _active_session and _active_session.status not in {"complete", "interrupted"}:
        _active_session.status = "stopped"
        _active_session.add_note("stop() called.")
    if DEBUG:
        print("[agent_loop] stop() called. Interpreter session cleared.")
