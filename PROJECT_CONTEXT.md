# PROJECT CONTEXT — AgentDesktopTest

> This is a living document. Entries are NEVER removed. All changes are timestamped.
> Paste this file + CONTRACTS.txt at the start of every AI coding session.

---

## CURRENT STATE (always reflects latest entry)

- **Agent Framework:** Open Interpreter (via Ollama backend)
- **Primary Model:** qwen2.5-coder:7b (Q4_K_M) via Ollama | ~4.3GB VRAM | real-world safe
- **Fallback Model:** deepseek-r1:8b (Q4_K_M) for heavy reasoning tasks
- **OS:** Windows 10 (build 10.0.26200) — hostname: FizzBeast
- **Python:** 3.11.9 at C:/Files311/
- **Project Root (local):** D:/AgentDesktopTest
- **GitHub:** https://github.com/Fizzolas/AgentDesktopTest (public)
- **Branch strategy:** main = stable | fix/* = per-session fix branches
- **config.py:** Complete — all 6 constants populated (2026-03-01 15:51 EST)
- **screen_capture.py:** Complete — capture_screen() implemented (2026-03-01 18:32 EST)
- **ollama_client.py:** Complete — query_model(), load_model(), check_ollama_running() implemented (2026-03-01 18:39 EST)
- **vision.py:** Complete — analyze_frame(), get_screen_state() implemented (2026-03-01 18:45 EST)
- **agent_loop.py:** Complete — run(), step(), stop() implemented (2026-03-01 18:54 EST)
- **Remaining empty shells:** main.py

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
| VRAM budget | ~6GB safe max for LLM (leave 2GB headroom) |

---

## MODEL SELECTION RATIONALE

- RTX 4070 Laptop = 8GB VRAM. Safe model size limit: ~6GB loaded weight.
- Qwen3-Coder:8b at Q4_K_M = ~5.0GB VRAM. Fits cleanly with headroom.
- Purpose-built for agentic + coding tasks. Long context window (128k).
- Open Interpreter's tool-calling loop benefits from models trained on code execution.
- DeepSeek-R1:8b kept as fallback for complex reasoning/debugging sessions.
- Do NOT load 14b+ models — they will exceed VRAM and spill to RAM, causing severe slowdown.

---

## FILE STRUCTURE & PURPOSE

| File | Purpose | Status |
|---|---|---|
| main.py | Entry point. Initializes config, starts agent via Open Interpreter | Empty shell |
| agent_loop.py | Core goal loop wrapping Open Interpreter session | **Complete** |
| vision.py | Vision pipeline. Screen frame analysis, returns structured data | **Complete** |
| screen_capture.py | Raw screen capture. Returns np.ndarray via mss | **Complete** |
| ollama_client.py | Ollama API interface. query_model(), load_model(), check_ollama_running() | **Complete** |
| config.py | Global constants. MODEL_NAME, OLLAMA_URL, SCREEN_REGION, LOOP_DELAY, MAX_RETRIES, DEBUG | Complete |
| PROJECT_CONTEXT.md | This file. Paste at session start | Active/Living |
| CONTRACTS.txt | Function contracts. Paste at session start | Complete |
| README.md | GitHub readme | Default |

---

## DEPENDENCY GRAPH

```
main.py
  imports: config.py, agent_loop.py

agent_loop.py
  imports: config.py (MODEL_NAME, OLLAMA_URL, LOOP_DELAY, DEBUG)
           vision.py (get_screen_state)
           ollama_client.py (check_ollama_running, query_model)
           open-interpreter (interpreter object)

vision.py
  imports: screen_capture.py, cv2, easyocr, numpy

screen_capture.py
  imports: mss (installed), numpy (installed)

ollama_client.py
  imports: config.py, requests (installed)

config.py
  imports: (none — base constants only)
```

---

## KNOWN FRAGILE AREAS

- config.py variable names are imported by ollama_client.py AND agent_loop.py. Rename = double break.
- screen_capture.py MUST return np.ndarray BGR (3-channel, uint8). vision.py depends on this type. Do not swap to PIL.Image or return BGRA.
- mss returns BGRA by default — the [:, :, :3] alpha strip in capture_screen() is intentional. Do not remove it.
- ollama_client.query_model() uses /api/chat with stream:False. Do NOT switch to /api/generate or enable streaming — return type must stay str.
- ollama_client.load_model() uses /api/generate with empty prompt + keep_alive. This is the correct Ollama warm-up pattern. Do not change the endpoint.
- query_model() calls check_ollama_running() at entry. Do not remove this guard — it is what raises ConnectionError per contract.
- vision._reader is initialized ONCE at module load (easyocr.Reader). Do NOT move it inside analyze_frame() — it would re-init the GPU model on every call.
- vision.analyze_frame() expects BGR np.ndarray input. Passing BGRA or PIL.Image will break the cv2 and EasyOCR pipeline.
- vision return dict keys are exactly: "description", "elements", "text". agent_loop.py keys into these by name. Do not rename.
- agent_loop interpreter is configured at module load. Do NOT re-configure in main.py or any other file.
- agent_loop.run() resets interpreter.messages = [] at start of every call — each goal gets a clean session.
- GOAL_COMPLETE is the completion signal string. run() checks "GOAL_COMPLETE" in action. Do not change this string.
- agent_loop._running is module-level state. stop() sets it False; run() reads it. Do not make it local.
- agent_loop.py is the ONLY file that calls vision.py and ollama_client.py. Not main.py.
- Open Interpreter object must be configured in agent_loop.py, not main.py.
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
- psutil 7.1.3
- open-interpreter 0.4.3 (installed 2026-03-01 16:10 EST — see changelog)

### Still needed
- Confirm: ollama running as local service on port 11434 (runtime check — not a pip package)

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
- Reasoning: RTX 4070 Laptop = 8GB VRAM. Qwen3-Coder:8b at Q4_K_M fits in ~5GB.
  Purpose-built for agentic coding tasks with 128k context. Best fit for Open Interpreter.
- Added DeepSeek-R1:8b as fallback for heavy reasoning sessions
- Added hardware profile section from pc_info_report.txt
- Confirmed pre-installed Python packages from pc_info_report.txt
- OS corrected: Windows 10 build 10.0.26200 (not Windows 11 as previously noted)
- Hostname confirmed: FizzBeast
- Python confirmed: 3.11.9 at C:/Files311/
- Restructured file as living/append-only changelog document
- Files affected: PROJECT_CONTEXT.md

### [2026-03-01 15:55 EST] — Model Correction: VRAM Budget Adjustment
- Clarified real-world VRAM budget: 8GB total, ~6GB available while agent is running
- Qwen3-Coder:8b Q4_K_M (~5GB weights) was too close to the ceiling under real load
- New primary model: **qwen2.5-coder:7b (Q4_K_M)** via Ollama
  - Weights: ~4.3GB VRAM, leaving ~1.7GB headroom for KV cache
  - Purpose-built for code generation, tool calling, and agentic tasks
  - Confirmed available on Ollama library, works with Open Interpreter natively
  - Ollama run command: `ollama run qwen2.5-coder:7b`
  - Open Interpreter flag: `interpreter --model ollama/qwen2.5-coder:7b`
- Fallback model unchanged: deepseek-r1:8b Q4_K_M (use only when 8b reasoning needed)
- Hard rule added: do NOT load any model whose Q4_K_M weights exceed 5.5GB
  - This leaves minimum 500MB headroom above the 6GB real-world budget
- Updated CURRENT STATE section to reflect new model
- Files affected: PROJECT_CONTEXT.md

### [2026-03-01 16:10 EST] — Open Interpreter Installed & Dependencies Resolved
- open-interpreter 0.4.3 successfully installed via pip
- Resolved starlette version conflict:
  - OI 0.4.3 requires starlette>=0.37.2,<0.38.0
  - sse-starlette required starlette>=0.49.1
  - fastapi 0.133.0 required starlette>=0.40.0
  - Fix: pinned starlette==0.37.2 and downgraded sse-starlette to <2.0.0
- pip check confirmed clean: No broken requirements
- Full confirmed installed stack for this project:
  open-interpreter 0.4.3, litellm 1.82.0, starlette 0.37.2,
  sse-starlette (compatible), anthropic 0.37.1, rich 13.9.4,
  tiktoken 0.7.0, gitpython 3.1.46, inquirer 3.4.1, yaspin 3.4.0
- Project is now ready for first code to be written into base files
- Next step: build config.py (all other files import from it)
- Files affected: PROJECT_CONTEXT.md

### [2026-03-01 15:51 EST] — config.py Populated | CONTRACTS.txt Finalized
- config.py written from empty shell to first working version
- All 6 constants defined and committed to main (commit: 83d812c):
  - MODEL_NAME: str = "qwen2.5-coder:7b"
    - Uses bare Ollama model name, NOT the OI-prefixed form
    - "ollama/qwen2.5-coder:7b" is for Open Interpreter CLI/code only — not raw Ollama HTTP API
  - OLLAMA_URL: str = "http://localhost:11434"
  - SCREEN_REGION: dict = {"top": 0, "left": 0, "width": 1920, "height": 1080}
    - Set to full primary monitor. Adjust if display resolution or multi-monitor config changes.
  - LOOP_DELAY: float = 2.0
    - Conservative starting tick rate. Tune down if agent feels sluggish, up if it over-polls.
  - MAX_RETRIES: int = 3
    - Standard retry floor for ollama_client.py query failure handling.
  - DEBUG: bool = False
    - Flip to True for verbose logging during active development/debugging sessions.
- Header comment in config.py updated to include MAX_RETRIES and DEBUG
  - Original empty shell header only listed 4 exports; CONTRACTS defines 6 — corrected.
- CONTRACTS.txt confirmed complete — all function contracts for all source files defined:
  - config.py (variables), screen_capture.py, vision.py, ollama_client.py, agent_loop.py, main.py
  - OI integration notes and full dependency chain summary included
  - Status updated: Skeleton → Complete
- open-interpreter 0.4.3 moved from "Still needed" to "Already installed" in DEPENDENCIES
  - Was installed in the 16:10 entry; "Still needed" entry was stale
- Files affected: config.py, PROJECT_CONTEXT.md

### [2026-03-01 18:32 EST] — screen_capture.py Complete
- screen_capture.py written from empty shell to first working version
- Implements capture_screen(region: dict | None = None) -> np.ndarray per contract
- Key implementation notes:
  - Uses mss.monitors[1] for primary monitor (index 0 = virtual combined monitor — not used)
  - mss returns BGRA by default; [:, :, :3] strips alpha channel to produce BGR np.ndarray
  - BGR output is required by vision.py and OpenCV downstream — do NOT change output format
  - Uses context manager (with mss.mss() as sct) to ensure handle release after every call
  - region=None path captures full primary monitor via SCREEN_REGION-equivalent defaults
- KNOWN FRAGILE note added: do not remove the [:, :, :3] alpha strip — it is intentional
- File status updated: Empty shell → Complete
- Files affected: screen_capture.py, PROJECT_CONTEXT.md, CONTRACTS.txt

### [2026-03-01 18:39 EST] — ollama_client.py Complete
- ollama_client.py written from empty shell to first working version
- Implements all 3 contracted functions: check_ollama_running(), load_model(), query_model()
- All 3 functions respect DEBUG flag from config.py for verbose print output
- File status updated: Empty shell → Complete
- Files affected: ollama_client.py, PROJECT_CONTEXT.md, CONTRACTS.txt

### [2026-03-01 18:45 EST] — vision.py Complete
- vision.py written from empty shell to first working version
- Implements analyze_frame() and get_screen_state() per contract
- EasyOCR reader (_reader) initialized ONCE at module load with gpu=True
- Element schema: {"type": str, "bbox": [x,y,w,h], "text": str, "confidence": float}
- File status updated: Empty shell → Complete
- Files affected: vision.py, PROJECT_CONTEXT.md, CONTRACTS.txt

### [2026-03-01 18:54 EST] — agent_loop.py Complete
- agent_loop.py written from empty shell to first working version
- Implements all 3 contracted functions:
  - run(goal: str) -> None
    - Resets interpreter.messages = [] and injects _SYSTEM_PROMPT at start of each call
    - Loops: get_screen_state() -> step() -> check for GOAL_COMPLETE -> sleep(LOOP_DELAY)
    - Exits on GOAL_COMPLETE signal, KeyboardInterrupt, or stop() call
    - Calls check_ollama_running() at entry — raises ConnectionError if Ollama not live
  - step(goal: str, screen_state: dict) -> str
    - Builds prompt from goal + screen_state["description"] + screen_state["text"][:500]
    - Routes through interpreter.chat() with display=DEBUG, stream=False
    - Walks response messages in reverse to extract last assistant content as action string
  - stop() -> None
    - Sets _running = False (run() exits on next iteration)
    - Clears interpreter.messages to free memory
- Open Interpreter configured at module load:
  - interpreter.llm.model = f"ollama/{MODEL_NAME}"
  - interpreter.llm.api_base = OLLAMA_URL
  - interpreter.auto_run = True (no confirmation prompts)
  - interpreter.verbose = DEBUG
  - interpreter.offline = True (local only, no cloud fallback)
- _SYSTEM_PROMPT defines agent role, step-by-step reasoning instruction, and GOAL_COMPLETE signal
- _running is module-level bool; shared between run() and stop()
- KNOWN FRAGILE notes added for interpreter config, session reset, GOAL_COMPLETE signal, _running state
- Dependency graph updated with explicit imports used
- File status updated: Empty shell → Complete
- Next step: main.py (final wiring layer)
- Files affected: agent_loop.py, PROJECT_CONTEXT.md, CONTRACTS.txt
