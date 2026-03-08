# runtime_models.py
# Role: Shared typed runtime models for the next-generation agent architecture.
# Imports from: dataclasses, enum, time, uuid, typing (stdlib only)
# Contract: ScreenElement, ScreenState, ToolCall, ToolResult, ModelReply,
#           AgentTask, SessionState, TaskStatus, TaskPriority, TaskKind,
#           create_task()
# NOTE: This file is intentionally dependency-light so every other project file
#       can adopt it without creating import cycles.
# NOTE: Legacy dict compatibility helpers are included to allow gradual migration.

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import time
from typing import Any
import uuid


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    WAITING = "waiting"
    BLOCKED = "blocked"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskPriority(int, Enum):
    LOW = 10
    NORMAL = 50
    HIGH = 90
    CRITICAL = 100


class TaskKind(str, Enum):
    PLAN = "plan"
    OBSERVE = "observe"
    THINK = "think"
    TOOL = "tool"
    VERIFY = "verify"
    RESPOND = "respond"
    COMPLETE = "complete"


@dataclass(slots=True)
class ScreenElement:
    type: str
    bbox: list[int]
    text: str = ""
    confidence: float = 0.0
    element_id: str = ""
    source: str = "vision"
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_legacy(cls, data: dict[str, Any]) -> "ScreenElement":
        bbox = data.get("bbox", [0, 0, 0, 0])
        return cls(
            type=str(data.get("type", "unknown")),
            bbox=[int(v) for v in bbox[:4]],
            text=str(data.get("text", "")),
            confidence=float(data.get("confidence", 0.0)),
            element_id=str(data.get("element_id", "")),
            source=str(data.get("source", "vision")),
            metadata=dict(data.get("metadata", {})),
        )

    def to_legacy(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "bbox": list(self.bbox),
            "text": self.text,
            "confidence": float(self.confidence),
        }


@dataclass(slots=True)
class ScreenState:
    description: str
    elements: list[ScreenElement] = field(default_factory=list)
    text: str = ""
    timestamp: float = field(default_factory=time.time)
    region: dict[str, int] | None = None
    active_window: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_legacy(cls, data: dict[str, Any]) -> "ScreenState":
        legacy_elements = data.get("elements", [])
        return cls(
            description=str(data.get("description", "")),
            elements=[ScreenElement.from_legacy(item) for item in legacy_elements],
            text=str(data.get("text", "")),
            timestamp=float(data.get("timestamp", time.time())),
            region=data.get("region"),
            active_window=str(data.get("active_window", "")),
            metadata=dict(data.get("metadata", {})),
        )

    def to_legacy(self) -> dict[str, Any]:
        return {
            "description": self.description,
            "elements": [element.to_legacy() for element in self.elements],
            "text": self.text,
        }

    def text_preview(self, limit: int = 500) -> str:
        return self.text[:limit]


@dataclass(slots=True)
class ToolCall:
    name: str
    arguments: dict[str, Any] = field(default_factory=dict)
    reason: str = ""
    call_id: str = field(default_factory=lambda: f"tool_{uuid.uuid4().hex[:10]}")


@dataclass(slots=True)
class ToolResult:
    tool_name: str
    success: bool
    output: str = ""
    error: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    call_id: str = ""
    timestamp: float = field(default_factory=time.time)


@dataclass(slots=True)
class ModelReply:
    content: str
    model_name: str = ""
    raw: Any = None
    tool_calls: list[ToolCall] = field(default_factory=list)
    stop_reason: str = ""
    usage: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def has_tool_calls(self) -> bool:
        return len(self.tool_calls) > 0


@dataclass(slots=True)
class AgentTask:
    title: str
    kind: TaskKind = TaskKind.THINK
    instructions: str = ""
    priority: TaskPriority = TaskPriority.NORMAL
    status: TaskStatus = TaskStatus.PENDING
    task_id: str = field(default_factory=lambda: f"task_{uuid.uuid4().hex[:10]}")
    parent_id: str | None = None
    depends_on: list[str] = field(default_factory=list)
    assigned_model: str = ""
    assigned_tool: str = ""
    attempts: int = 0
    max_attempts: int = 3
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    context: dict[str, Any] = field(default_factory=dict)
    result: ToolResult | None = None
    notes: list[str] = field(default_factory=list)

    def touch(self) -> None:
        self.updated_at = time.time()

    def add_note(self, note: str) -> None:
        self.notes.append(note)
        self.touch()

    def mark_running(self) -> None:
        self.status = TaskStatus.RUNNING
        self.attempts += 1
        self.touch()

    def mark_done(self) -> None:
        self.status = TaskStatus.DONE
        self.touch()

    def mark_failed(self, note: str = "") -> None:
        self.status = TaskStatus.FAILED
        if note:
            self.notes.append(note)
        self.touch()


@dataclass(slots=True)
class SessionState:
    goal: str
    session_id: str = field(default_factory=lambda: f"session_{uuid.uuid4().hex[:10]}")
    created_at: float = field(default_factory=time.time)
    active_model: str = ""
    planner_model: str = ""
    executor_model: str = ""
    status: str = "idle"
    last_screen_state: ScreenState | None = None
    task_queue: list[AgentTask] = field(default_factory=list)
    completed_tasks: list[AgentTask] = field(default_factory=list)
    failed_tasks: list[AgentTask] = field(default_factory=list)
    tool_history: list[ToolResult] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def enqueue(self, task: AgentTask) -> None:
        self.task_queue.append(task)
        self.task_queue.sort(key=lambda item: int(item.priority), reverse=True)

    def pop_next_task(self) -> AgentTask | None:
        if not self.task_queue:
            return None
        return self.task_queue.pop(0)

    def record_completed(self, task: AgentTask) -> None:
        task.mark_done()
        self.completed_tasks.append(task)

    def record_failed(self, task: AgentTask, note: str = "") -> None:
        task.mark_failed(note)
        self.failed_tasks.append(task)

    def add_tool_result(self, result: ToolResult) -> None:
        self.tool_history.append(result)

    def add_note(self, note: str) -> None:
        self.notes.append(note)


def create_task(
    title: str,
    instructions: str,
    kind: TaskKind = TaskKind.THINK,
    priority: TaskPriority = TaskPriority.NORMAL,
    **context: Any,
) -> AgentTask:
    return AgentTask(
        title=title,
        instructions=instructions,
        kind=kind,
        priority=priority,
        context=context,
    )
