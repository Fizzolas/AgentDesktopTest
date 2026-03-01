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
- **All base files:** created as empty shells (see File Structure below)

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
| agent_loop.py | Core goal loop wrapping Open Interpreter session | Empty shell |
| vision.py | Vision pipeline. Screen frame analysis, returns structured data | Empty shell |
| screen_capture.py | Raw screen capture. Returns np.ndarray via mss | Empty shell |
| ollama_client.py | Ollama API interface. query_model(), load_model() | Empty shell |
| config.py | Global constants. MODEL_NAME, OLLAMA_URL, SCREEN_REGION, LOOP_DELAY | Empty shell |
| PROJECT_CONTEXT.md | This file. Paste at session start | Active/Living |
| CONTRACTS.txt | Function contracts. Paste at session start | Skeleton |
| README.md | GitHub readme | Default |

---

## DEPENDENCY GRAPH

```
main.py
  imports: config.py, agent_loop.py

agent_loop.py
  imports: config.py, vision.py, ollama_client.py, screen_capture.py
  also wraps: open-interpreter (interpreter object)

vision.py
  imports: screen_capture.py

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
- screen_capture.py MUST return np.ndarray. vision.py depends on this type. Do not swap to PIL.Image.
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

### Still needed
- open-interpreter (pip install open-interpreter)
- Confirm: ollama running as local service on port 11434

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
