# PROJECT CONTEXT — AgentDesktopTest

> This is a living document. Entries are NEVER removed. All changes are timestamped.
> Paste this file + CONTRACTS.txt at the start of every AI coding session.

---

## CURRENT STATE (always reflects latest entry)

- **Agent Framework:** Open Interpreter (via Ollama backend) with typed session/queue scaffold now active under the legacy loop
- **Primary Model:** qwen2.5-coder:7b (Q4_K_M) via Ollama | GPU-only with RAM offloading
- **Fallback Model:** deepseek-r1:8b (Q4_K_M) for heavy reasoning tasks
- **Memory Strategy:** GPU-only compute, RAM weight offloading enabled, CPU compute blocked
- **Monitoring:** monitor.py tracks Ollama, system resources, GPU stats → monitor.log (rolling, 10MB max)
- **OS:** Windows 10 (build 10.0.26200) — hostname: FizzBeast
- **Python:** 3.11.9 at C:/Files311/
- **Project Root (local):** D:/AgentDesktopTest
- **GitHub:** https://github.com/Fizzolas/AgentDesktopTest (public)
- **Branch strategy:** main = stable | fix/* = per-session fix branches
- **Current refactor branch:** fix/runtime-baseline-01
- **Baseline refactor phase:** Phase 3 complete — active loop now stores typed SessionState and internal AgentTask queue
- **config.py:** Complete — 8 constants (added BLOCK_CPU_COMPUTE, OLLAMA_NUM_GPU) (2026-03-01 19:20 EST)
- **runtime_models.py:** Complete — shared dataclasses/enums/helpers for queue-based runtime (2026-03-08 10:07 EST)
- **model_adapter.py:** Complete — backend adapter boundary for model-agnostic runtime migration (2026-03-08 10:32 EST)
- **screen_capture.py:** Complete — capture_screen() implemented (2026-03-01 18:32 EST)
- **ollama_client.py:** Complete — query_model(), load_model(), check_ollama_running() implemented; typed query_model_reply() added (2026-03-08 10:32 EST)
- **vision.py:** Complete — analyze_frame(), get_screen_state() implemented, EasyOCR gpu=True (2026-03-01 18:45 EST)
- **agent_loop.py:** Complete — run(), step(), stop() still active; now also manages typed session state, queue seeding, and live session snapshots (2026-03-08 10:50 EST)
- **main.py:** Complete — main() implemented (2026-03-01 18:59 EST)
- **monitor.py:** Complete — system health monitoring with rolling log (2026-03-01 19:29 EST)
- **Remaining empty shells:** NONE — all files complete
- **Next migration target:** vision.py should emit typed ScreenState directly and begin supporting richer frame-to-frame UI memory

---

## HARDWARE PROFILE

| Component | Detail |
|---|---|
| CPU | Intel i7-13620H, 10 cores / 16 logical, 2.4GHz |
| RAM | 32GB DDR5 5600MHz (2x 16GB) |
| GPU | NVIDIA RTX 4070 Laptop GPU, 8GB VRAM |
| iGPU | Intel UHD (2GB, not used for inference) |
| Storage C: | 926GB NVMe WD SN560 (748GB used, 178GB free) |
| Storage D: | 476GB NVMe Kingston (296GB used, 180GB free) |
| VRAM budget | No hard limit — RAM offloading enabled for oversized models |

---

## MODEL SELECTION RATIONALE

- RTX 4070 Laptop = 8GB VRAM with 32GB RAM available for offloading.
- GPU-only compute enforced — CPU is blocked from performing ANY GPU calculations.
- Ollama configured with num_gpu=999 to force all layers to GPU with automatic RAM offload.
- CUDA environment variables block CPU fallback: CUDA_LAUNCH_BLOCKING=1, CUDA_VISIBLE_DEVICES=0.
- EasyOCR runs on GPU (gpu=True) for vision pipeline.
- Models larger than VRAM will use RAM offloading without falling back to CPU compute.
- Purpose-built for agentic + coding tasks. Long context window (128k).
- Open Interpreter's tool-calling loop benefits from models trained on code execution.

---

## FILE STRUCTURE & PURPOSE

| File | Purpose | Status |
|---|---|---|
| main.py | Entry point. Initializes config, starts agent via Open Interpreter | **Complete** |
| agent_loop.py | Core goal loop with typed session state, internal queue scaffolding, and Open Interpreter execution | **Complete** |
| runtime_models.py | Shared typed runtime layer for queue tasks, model replies, tool results, and session state | **Complete** |
| model_adapter.py | Stable backend boundary for future multi-runtime model support | **Complete** |
| vision.py | Vision pipeline. Screen frame analysis, still returning legacy dict state | **Complete** |
| screen_capture.py | Raw screen capture. Returns np.ndarray via mss | **Complete** |
| ollama_client.py | Ollama API interface. query_model(), query_model_reply(), load_model(), check_ollama_running() | **Complete** |
| config.py | Global constants. MODEL_NAME, OLLAMA_URL, SCREEN_REGION, LOOP_DELAY, MAX_RETRIES, DEBUG, BLOCK_CPU_COMPUTE, OLLAMA_NUM_GPU | **Complete** |
| monitor.py | System health monitor. Tracks Ollama, resources, GPU. Writes monitor.log | **Complete** |
| PROJECT_CONTEXT.md | This file. Paste at session start | Active/Living |
| CONTRACTS.txt | Function contracts. Paste at session start | Complete |
| README.md | GitHub readme | Default |

---

## DEPENDENCY GRAPH

```
runtime_models.py
  imports: dataclasses, enum, time, uuid, typing (stdlib only)

model_adapter.py
  imports: config.py, ollama_client.py, runtime_models.py

main.py
  imports: config.py (DEBUG, MODEL_NAME, OLLAMA_URL)
           agent_loop.py (run)
           ollama_client.py (check_ollama_running, load_model) [startup only]

agent_loop.py
  imports: config.py (MODEL_NAME, OLLAMA_URL, LOOP_DELAY, DEBUG, BLOCK_CPU_COMPUTE, OLLAMA_NUM_GPU)
           model_adapter.py (build_default_adapter)
           runtime_models.py (AgentTask, ScreenState, SessionState, TaskKind, TaskPriority, create_task)
           vision.py (get_screen_state)
           open-interpreter (interpreter object)
           time (stdlib)
           os (stdlib)
           typing (stdlib)

vision.py
  imports: screen_capture.py, cv2, easyocr, numpy

screen_capture.py
  imports: mss (installed), numpy (installed)

ollama_client.py
  imports: config.py, requests (installed), runtime_models.py

monitor.py
  imports: config.py (OLLAMA_URL, MODEL_NAME, DEBUG)
           psutil, requests, time, threading, os, json, pathlib

config.py
  imports: (none — base constants only)
```

---

## KNOWN FRAGILE AREAS

- config.py variable names are imported by ollama_client.py AND agent_loop.py AND main.py AND monitor.py. Rename = quadruple break.
- config.py BLOCK_CPU_COMPUTE and OLLAMA_NUM_GPU control critical GPU/RAM behavior. Do not modify without understanding implications.
- agent_loop.py sets CUDA environment variables at module load. These MUST execute before interpreter initialization.
- CUDA_VISIBLE_DEVICES=0 hardcoded to RTX 4070 (GPU 0). Multi-GPU systems need adjustment.
- OLLAMA_NUM_GPU=999 is intentional — signals unlimited GPU layers with RAM offload fallback.
- screen_capture.py MUST return np.ndarray BGR (3-channel, uint8). vision.py depends on this type. Do not swap to PIL.Image or return BGRA.
- mss returns BGRA by default — the [:, :, :3] alpha strip in capture_screen() is intentional. Do not remove it.
- ollama_client.query_model() remains the legacy plain-string wrapper. Prefer query_model_reply() or model_adapter.py for new runtime code.
- vision._reader is initialized ONCE at module load (easyocr.Reader with gpu=True). Do NOT move it inside analyze_frame() — it would re-init the GPU model on every call.
- vision.analyze_frame() expects BGR np.ndarray input. Passing BGRA or PIL.Image will break the cv2 and EasyOCR pipeline.
- vision return dict keys are exactly: "description", "elements", "text". agent_loop.py now normalizes them into ScreenState, but raw legacy keys still must remain stable until vision migration is complete.
- agent_loop interpreter is configured at module load. Do NOT re-configure in main.py or any other file until bootstrap extraction is implemented.
- GOAL_COMPLETE is still the completion signal string. The internal task queue now exists, but explicit task-state completion has not fully replaced this string yet.
- agent_loop._active_session stores the live typed SessionState; get_session_snapshot() exposes a serializable debug view.
- monitor.py runs in a daemon thread. It does NOT block main execution. Can be run standalone: python monitor.py
- monitor.log auto-rotates at 10MB. Old log becomes monitor.log.old (single backup only).
- Do not add pip packages without logging them below in the active Dependencies section.

---

## DEPENDENCIES

### Already installed (confirmed from pc_info_report.txt 2026-03-01)
- mss 10.1.0
- numpy 2.2.6
- pillow 12.1.1
- pyautogui 0.9.54
- opencv-python 4.12.0.88
- easyocr 1.7.2
- requests (via httpx 0.28.1)
- keyboard 0.13.5
- openai 2.24.0 (available if needed for OI API compat)
- psutil 7.1.3 (used by monitor.py)
- open-interpreter 0.4.3 (installed 2026-03-01 16:10 EST — see changelog)

### Still needed
- Confirm: ollama running as local service on port 11434 (runtime check — not a pip package)
- Optional: nvidia-smi in PATH for GPU stats in monitor.py (auto-detected)

---

## AI SESSION RULES

1. Paste this file AND CONTRACTS.txt at the start of every session before any code changes.
2. Only modify files explicitly named in the request. Touch nothing else.
3. State the branch at session start (e.g. "on branch fix/agent-loop").
4. Output fixes as diff-style changed lines only (+/-), not full file rewrites.
5. Confirm any new file against CONTRACTS.txt before writing it.
6. Before fixing a bug: explain root cause + blast radius, THEN provide the fix.
7. One interdependent file pair max per session.
8. If a model or tool changes, update this file's CHANGELOG and CURRENT STATE immediately.

---

## CHANGELOG

### [2026-03-08 10:50 EST] — Baseline Refactor Phase 3: Typed Session State + Queue Scaffold Activated
- Refactored agent_loop.py to use typed SessionState and ScreenState under the active runtime
- Added internal queue scaffolding in agent_loop.py using AgentTask, TaskKind, TaskPriority, and create_task()
- Added session creation, task seeding, follow-up task scheduling, and task completion recording helpers
- step() now accepts either legacy dict screen state or typed ScreenState and normalizes to ScreenState internally
- run() now validates backend availability through model_adapter.build_default_adapter() rather than calling the legacy backend function directly
- Added get_session_snapshot() export for future UI/task-inspection tooling
- Preserved existing Open Interpreter execution behavior and legacy GOAL_COMPLETE completion signal
- No external tool capability removed in this phase
- Files affected: agent_loop.py, PROJECT_CONTEXT.md, CONTRACTS.txt

### [2026-03-08 10:07 EST] — Baseline Refactor Phase 1: Shared Runtime Types Added
- Created new file: runtime_models.py
- Added shared enums for task lifecycle, task priority, and task kind
- Added dataclasses for ScreenElement, ScreenState, ToolCall, ToolResult, ModelReply, AgentTask, and SessionState
- Added create_task() helper for future queue-based runtime
- Added legacy compatibility helpers so dict-based vision/model state can be migrated gradually without breaking the working prototype
- Updated CONTRACTS.txt to document runtime_models.py as the new shared baseline layer
- No active runtime behavior changed in this phase
- No existing imports were changed in this phase
- Purpose: establish a safe typed foundation for the upcoming backend adapter, task queue, and planner/executor split
- Files affected: runtime_models.py, PROJECT_CONTEXT.md, CONTRACTS.txt

### [2026-03-01 15:16 EST] — Initial Setup
- Created GitHub repo: Fizzolas/AgentDesktopTest (public)
- Created all base files as empty shells with header comments:
  main.py, agent_loop.py, vision.py, screen_capture.py,
  ollama_client.py, config.py, PROJECT_CONTEXT.md, CONTRACTS.txt, README.md
- Defined dependency graph and import chain
- Set primary model target as MiniCPM-V (placeholder, now superseded)
- Established AI session rules and fragile area documentation
- Files affected: ALL

### [2026-03-01 15:45 EST] — Framework + Model Update
- Confirmed agent framework: Open Interpreter (not raw Agent S3)
- Replaced MiniCPM-V model target with Qwen3-Coder:8b Q4_K_M via Ollama
- Added hardware profile, confirmed packages, corrected OS to Windows 10 build 10.0.26200
- Restructured file as living/append-only changelog document
- Files affected: PROJECT_CONTEXT.md

### [2026-03-01 15:55 EST] — Model Correction: VRAM Budget Adjustment
- New primary model: qwen2.5-coder:7b (Q4_K_M) — ~4.3GB VRAM, safe headroom
- Hard rule: do NOT load any model whose Q4_K_M weights exceed 5.5GB
- Files affected: PROJECT_CONTEXT.md

### [2026-03-01 16:10 EST] — Open Interpreter Installed & Dependencies Resolved
- open-interpreter 0.4.3 successfully installed via pip
- Resolved starlette version conflict; pip check confirmed clean
- Files affected: PROJECT_CONTEXT.md

### [2026-03-01 15:51 EST] — config.py Populated | CONTRACTS.txt Finalized
- All 6 constants defined: MODEL_NAME, OLLAMA_URL, SCREEN_REGION, LOOP_DELAY, MAX_RETRIES, DEBUG
- CONTRACTS.txt confirmed complete for all source files
- Files affected: config.py, PROJECT_CONTEXT.md

### [2026-03-01 18:32 EST] — screen_capture.py Complete
- Implements capture_screen(region: dict | None = None) -> np.ndarray
- mss context manager; BGRA → BGR strip; primary monitor via monitors[1]
- Files affected: screen_capture.py, PROJECT_CONTEXT.md, CONTRACTS.txt

### [2026-03-01 18:39 EST] — ollama_client.py Complete
- Implements check_ollama_running(), load_model(), query_model()
- Files affected: ollama_client.py, PROJECT_CONTEXT.md, CONTRACTS.txt

### [2026-03-01 18:45 EST] — vision.py Complete
- Implements analyze_frame() and get_screen_state()
- EasyOCR + OpenCV two-pass analysis; _reader at module level with gpu=True
- Files affected: vision.py, PROJECT_CONTEXT.md, CONTRACTS.txt

### [2026-03-01 18:54 EST] — agent_loop.py Complete
- Implements run(), step(), stop()
- OI configured at module load; auto_run=True; offline=True
- GOAL_COMPLETE signal; _running module-level state; fresh session per run()
- Files affected: agent_loop.py, PROJECT_CONTEXT.md, CONTRACTS.txt

### [2026-03-01 18:59 EST] — main.py Complete | ALL FILES COMPLETE
- Implements main() — startup banner, Ollama check, model warm-up, goal prompt, agent_loop.run()
- Imports ollama_client for startup check/warm-up only (not runtime use)
- ConnectionError and unexpected exceptions caught with clean exit messages
- DEBUG=True re-raises unexpected exceptions for full traceback
- CONTRACTS.txt updated: main.py Imports From clarified to include ollama_client startup use
- Dependency graph updated to reflect actual main.py imports
- KNOWN FRAGILE updated: config.py rename now triple-break; main.py/ollama_client boundary noted
- All file statuses updated to Complete
- Files affected: main.py, PROJECT_CONTEXT.md, CONTRACTS.txt

### [2026-03-01 19:21 EST] — GPU-Only Compute + RAM Offloading Enforced
- config.py: Added BLOCK_CPU_COMPUTE=True and OLLAMA_NUM_GPU=999
- agent_loop.py: Set CUDA environment variables to block CPU compute fallback
- CUDA_LAUNCH_BLOCKING=1, CUDA_VISIBLE_DEVICES=0, OMP_NUM_THREADS=1, MKL_NUM_THREADS=1
- interpreter.llm.num_gpu=999 forces all layers to GPU with RAM offload if VRAM insufficient
- EasyOCR remains gpu=True in vision.py
- VRAM budget removed — RAM offloading handles oversized models
- Memory strategy: GPU-only inference, RAM weight offloading, zero CPU compute
- Files affected: config.py, agent_loop.py, PROJECT_CONTEXT.md, CONTRACTS.txt

### [2026-03-01 19:29 EST] — System Monitor Added
- monitor.py: Background health monitor tracking Ollama, system resources, GPU stats
- Runs in daemon thread, writes to monitor.log (rolling 10MB limit, single backup)
- Logs: Ollama reachability/response time, model load status, RAM/CPU/GPU usage, temperature
- Warnings: Ollama slow/unreachable, high RAM (>90%), high GPU util (>95%), high temp (>85°C)
- Periodic snapshots every ~25 seconds with full system state
- Can be run standalone: python monitor.py (Ctrl+C to stop)
- Standalone mode does NOT start agent loop — monitor only
- Files affected: monitor.py, PROJECT_CONTEXT.md
