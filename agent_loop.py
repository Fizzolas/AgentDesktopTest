# agent_loop.py
# Role: Core autonomous goal loop. Orchestrates all components.
# Imports from: config.py, vision.py, model_adapter.py, runtime_models.py, open-interpreter
# Contract: run(goal: str) -> None
#           step(goal: str, screen_state: dict | ScreenState | None = None) -> str
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

from bootstrap import ensure_runtime_dependencies
from config import (
    MODEL_NAME,
    OLLAMA_URL,
    LOOP_DELAY,
    DEBUG,
    BLOCK_CPU_COMPUTE,
    OLLAMA_NUM_GPU,
    ACTIVE_TOOL_PROVIDER,
    ENABLE_OPEN_INTERPRETER_TOOLS,
    ENABLE_AGENTS2_S3_TOOLS,
    AUTO_TOOL_SELECTION,
    ADAPTIVE_VISION,
)
from model_adapter import build_default_adapter
from runtime_models import AgentTask, ScreenState, SessionState, TaskKind, TaskPriority, create_task
from vision import get_screen_state

_dependency_status = ensure_runtime_dependencies()

try:
    from interpreter import interpreter
except Exception as e:
    raise RuntimeError(
        "Open Interpreter import failed inside the prepared virtual environment. "
        f"Underlying error: {e}"
    ) from e

if BLOCK_CPU_COMPUTE:
    os.environ["CUDA_LAUNCH_BLOCKING"] = "1"
    os.environ["CUDA_DEVICE_ORDER"] = "PCI_BUS_ID"
    os.environ["CUDA_VISIBLE_DEVICES"] = "0"
    os.environ["OMP_NUM_THREADS"] = "1"
    os.environ["MKL_NUM_THREADS"] = "1"
    if DEBUG:
        print("[agent_loop] CPU compute blocked. GPU-only mode enforced.")

interpreter.llm.model = f"ollama/{MODEL_NAME}"
interpreter.llm.api_base = OLLAMA_URL
interpreter.auto_run = True
interpreter.verbose = DEBUG
interpreter.offline = True
interpreter.llm.num_gpu = OLLAMA_NUM_GPU

if DEBUG:
    print(f"[agent_loop] Ollama config: num_gpu={OLLAMA_NUM_GPU} (RAM offload enabled if needed)")

_model_adapter = build_default_adapter()
_running = False
_active_session: SessionState | None = None
_last_action: str = ""
_last_tool_route: str = "planner"
_last_vision_reason: str = ""

_SYSTEM_PROMPT = """
You are an autonomous desktop agent running on a Windows 10 machine.
You observe the current screen state and take actions to accomplish the user's goal.
You have access to Python and shell execution via Open Interpreter.
Always reason step by step. After each action, wait for screen feedback before proceeding.
When the goal is fully accomplished, respond with exactly: GOAL_COMPLETE
""".strip()


_COMMAND_KEYWORDS = {
    "click", "type", "press", "open", "launch", "run", "execute", "create", "delete", "move",
    "rename", "install", "save", "close", "scroll", "send", "paste", "copy", "drag",
}
_VISUAL_KEYWORDS = {
    "look", "see", "visible", "screen", "window", "dialog", "button", "menu", "icon",
    "text on screen", "ui", "desktop", "verify", "confirm", "read", "capture",
}
_COMPLEXITY_KEYWORDS = {
    "multi-step", "complex", "analyze", "plan", "research", "debug", "workflow", "sequence",
    "orchestrate", "refactor", "architecture",
}



def _tool_provider_note() -> str:
    notes = [f"ACTIVE TOOL PROVIDER SETTING: {ACTIVE_TOOL_PROVIDER}"]
    notes.append(f"OPEN_INTERPRETER TOOLS ENABLED: {ENABLE_OPEN_INTERPRETER_TOOLS}")
    notes.append(f"AGENTS2_S3 TOOLS ENABLED: {ENABLE_AGENTS2_S3_TOOLS}")
    notes.append(f"BOOTSTRAP ACTIVE PROVIDER: {_dependency_status.get('active_provider', 'unknown')}")
    notes.append(f"AUTO TOOL SELECTION: {AUTO_TOOL_SELECTION}")
    notes.append(f"ADAPTIVE VISION: {ADAPTIVE_VISION}")
    return "\n".join(notes)



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
    session.metadata["tool_provider"] = _dependency_status.get("active_provider", ACTIVE_TOOL_PROVIDER)
    session.metadata["auto_tool_selection"] = AUTO_TOOL_SELECTION
    session.metadata["adaptive_vision"] = ADAPTIVE_VISION
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



def _classify_task_complexity(task: AgentTask) -> str:
    text = f"{task.title} {task.instructions}".lower()
    score = 0
    if task.kind in {TaskKind.PLAN, TaskKind.VERIFY}:
        score += 1
    if task.kind in {TaskKind.TOOL, TaskKind.THINK}:
        score += 2
    if len(text) > 180:
        score += 1
    if any(word in text for word in _COMPLEXITY_KEYWORDS):
        score += 2
    if any(word in text for word in _COMMAND_KEYWORDS):
        score += 1
    if score >= 4:
        return "high"
    if score >= 2:
        return "medium"
    return "low"



def _task_requires_vision(task: AgentTask, goal: str, session: SessionState) -> tuple[bool, str]:
    if not ADAPTIVE_VISION:
        return True, "adaptive vision disabled"

    text = f"{goal} {task.title} {task.instructions}".lower()
    if task.kind in {TaskKind.OBSERVE, TaskKind.VERIFY}:
        return True, f"task kind {task.kind.value} requires current visual confirmation"
    if any(word in text for word in _VISUAL_KEYWORDS):
        return True, "goal/task references visible UI state"
    if session.last_screen_state is None:
        return True, "no cached screen state available yet"
    return False, "reusing cached screen state for non-visual task"



def _select_execution_route(task: AgentTask, dependency_status: dict) -> tuple[str, str]:
    complexity = _classify_task_complexity(task)
    requested_provider = dependency_status.get("active_provider", ACTIVE_TOOL_PROVIDER)
    agents_ready = dependency_status.get("providers", {}).get("agents2_s3", {}).get("installed", False)
    open_interpreter_ready = dependency_status.get("providers", {}).get("open_interpreter", {}).get("installed", False)

    if not AUTO_TOOL_SELECTION:
        if task.kind in {TaskKind.OBSERVE, TaskKind.PLAN, TaskKind.VERIFY, TaskKind.RESPOND}:
            return "planner", f"auto tool selection disabled; {task.kind.value} uses planner/model adapter"
        return "open_interpreter", "auto tool selection disabled; execution tasks use Open Interpreter"

    if task.kind in {TaskKind.OBSERVE, TaskKind.PLAN, TaskKind.VERIFY, TaskKind.RESPOND}:
        return "planner", f"{task.kind.value} is reasoning/inspection only"

    if task.kind == TaskKind.TOOL:
        if requested_provider == "agents2_s3" and agents_ready:
            return "agents2_s3_fallback", "agents2-s3 selected for tool orchestration; safe execution fallback remains Open Interpreter"
        if open_interpreter_ready:
            return "open_interpreter", "tool task requires executable command routing"
        return "planner", "tool task downgraded because executable backend is unavailable"

    if task.kind == TaskKind.THINK:
        if complexity == "low":
            return "planner", "low-complexity think task routed to model adapter only"
        if requested_provider == "agents2_s3" and agents_ready:
            return "agents2_s3_fallback", "higher-complexity think task tagged for agents2-s3 style orchestration with safe Open Interpreter execution fallback"
        if open_interpreter_ready:
            return "open_interpreter", "higher-complexity think task may need command execution"
        return "planner", "higher-complexity think task downgraded because executable backend is unavailable"

    return "planner", "default planner route"



def _build_prompt(goal: str, session: SessionState, task: AgentTask, screen_state: ScreenState, route: str, route_reason: str) -> str:
    prompt_parts = [
        f"GOAL: {goal}",
        f"SESSION_ID: {session.session_id}",
        f"ACTIVE MODEL: {session.active_model}",
        f"CURRENT TASK: {task.title}",
        f"TASK KIND: {task.kind.value}",
        f"TASK INSTRUCTIONS: {task.instructions}",
        f"EXECUTION ROUTE: {route}",
        f"ROUTE REASON: {route_reason}",
        f"CURRENT SCREEN: {screen_state.description or 'No screen data available.'}",
        _tool_provider_note(),
    ]

    visible_text = screen_state.text_preview(500)
    if visible_text:
        prompt_parts.append(f"VISIBLE TEXT: {visible_text}")

    if _last_action:
        prompt_parts.append(f"LAST ACTION SUMMARY: {_last_action[:600]}")

    prompt_parts.append(f"COMPLETED TASKS: {len(session.completed_tasks)}")
    prompt_parts.append("PENDING TASK QUEUE:")
    prompt_parts.append(_queue_preview(session))

    if route == "planner":
        prompt_parts.append(
            "Do not invent shell commands. Return only a concise plan, analysis, or verification result for this task. "
            "If an actual desktop command is needed next, say so clearly in plain text."
        )
    else:
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



def _record_completed_task(session: SessionState, task: AgentTask, action: str, route: str, route_reason: str) -> None:
    note = action[:800] if action else "No assistant action content returned."
    task.add_note(note)
    task.assigned_tool = route
    task.context["route_reason"] = route_reason
    session.record_completed(task)
    session.metadata["last_completed_task_id"] = task.task_id
    session.metadata["last_route"] = route
    session.metadata["last_route_reason"] = route_reason
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



def _get_relevant_screen_state(goal: str, task: AgentTask, provided_state: dict | ScreenState | None, session: SessionState) -> ScreenState:
    global _last_vision_reason

    if provided_state is not None:
        state = _normalize_screen_state(provided_state)
        _last_vision_reason = "screen state provided by caller"
        return state

    needs_vision, reason = _task_requires_vision(task, goal, session)
    _last_vision_reason = reason
    if needs_vision:
        return _normalize_screen_state(get_screen_state())
    if session.last_screen_state is not None:
        return session.last_screen_state
    return _normalize_screen_state(get_screen_state())



def _run_task_with_route(prompt: str, route: str) -> str:
    if route == "planner":
        return _model_adapter.generate_text(prompt=prompt, system=_SYSTEM_PROMPT, timeout=60)

    if route == "agents2_s3_fallback":
        guidance = _model_adapter.generate_text(
            prompt=(
                prompt
                + "\n\nBefore any action, briefly restate the intended high-level orchestration in 1-2 sentences."
            ),
            system=_SYSTEM_PROMPT,
            timeout=60,
        )
        response_messages = interpreter.chat(
            prompt + "\n\nPlanned orchestration guidance:\n" + guidance,
            display=DEBUG,
            stream=False,
        )
        return _extract_action(response_messages)

    response_messages = interpreter.chat(prompt, display=DEBUG, stream=False)
    return _extract_action(response_messages)



def step(goal: str, screen_state: dict | ScreenState | None = None) -> str:
    global _active_session, _last_action, _last_tool_route, _dependency_status

    session = _active_session if _active_session and _active_session.goal == goal else _make_session(goal)
    _active_session = session
    session.status = "running"

    task = _next_task(session)
    runtime_screen_state = _get_relevant_screen_state(goal, task, screen_state, session)
    session.last_screen_state = runtime_screen_state

    route, route_reason = _select_execution_route(task, _dependency_status)
    task.assigned_tool = route
    task.context["route_reason"] = route_reason
    task.context["vision_reason"] = _last_vision_reason

    prompt = _build_prompt(goal, session, task, runtime_screen_state, route, route_reason)

    if DEBUG:
        print(f"[agent_loop] step() task: {task.kind.value} :: {task.title}")
        print(f"[agent_loop] step() route: {route} :: {route_reason}")
        print(f"[agent_loop] step() vision: {_last_vision_reason}")

    action = _run_task_with_route(prompt, route)
    _last_action = action
    _last_tool_route = route

    _record_completed_task(session, task, action, route, route_reason)
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
    global _running, _active_session, _last_action, _dependency_status, _last_tool_route

    _dependency_status = ensure_runtime_dependencies()
    if not _dependency_status.get("providers", {}).get("open_interpreter", {}).get("installed"):
        error = _dependency_status.get("providers", {}).get("open_interpreter", {}).get("error", "unknown import failure")
        raise RuntimeError(f"Open Interpreter is not usable in this environment: {error}")

    if not _model_adapter.is_available():
        raise ConnectionError("Ollama is not reachable. Start Ollama before calling agent_loop.run().")

    interpreter.messages = []
    interpreter.system_message = _SYSTEM_PROMPT

    _active_session = _make_session(goal)
    _last_action = ""
    _last_tool_route = "planner"
    _running = True
    tick = 0

    print(f"[agent_loop] Starting. Goal: {goal}")

    try:
        while _running:
            tick += 1
            if DEBUG:
                print(f"[agent_loop] Tick {tick}")
            action = step(goal)

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
    session = _active_session
    if session is None:
        return {
            "active": False,
            "running": _running,
            "last_action": _last_action,
            "tool_provider": _dependency_status.get("active_provider", ACTIVE_TOOL_PROVIDER),
            "last_route": _last_tool_route,
            "last_vision_reason": _last_vision_reason,
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
        "tool_provider": session.metadata.get("tool_provider", _dependency_status.get("active_provider", ACTIVE_TOOL_PROVIDER)),
        "last_route": session.metadata.get("last_route", _last_tool_route),
        "last_route_reason": session.metadata.get("last_route_reason", ""),
        "last_vision_reason": _last_vision_reason,
        "last_screen_state": session.last_screen_state.to_legacy() if session.last_screen_state else None,
        "pending_tasks": [_task_to_dict(task) for task in session.task_queue],
        "completed_tasks": [_task_to_dict(task) for task in session.completed_tasks[-10:]],
        "notes": list(session.notes[-20:]),
        "metadata": dict(session.metadata),
    }



def stop() -> None:
    global _running
    _running = False
    interpreter.messages = []
    if _active_session and _active_session.status not in {"complete", "interrupted"}:
        _active_session.status = "stopped"
        _active_session.add_note("stop() called.")
    if DEBUG:
        print("[agent_loop] stop() called. Interpreter session cleared.")
