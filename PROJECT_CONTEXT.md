# PROJECT CONTEXT — AgentDesktopTest

## Last Updated
2026-03-01 | Author: Fizzolas

---

## Project Overview
A local desktop AI agent built in Python that can autonomously observe and interact with a Windows 11 PC using vision, goal-based reasoning, and a locally hosted LLM via Ollama. The agent captures the screen, analyzes it, queries the local model, and takes action in a continuous loop.

---

## Environment
- OS: Windows 11
- Local model runtime: Ollama (also LM Studio available)
- Primary model target: MiniCPM-V or similar vision-capable local model
- Root project directory on local machine: D:/
- GitHub repo: https://github.com/Fizzolas/AgentDesktopTest (public)
- Branch strategy: main for stable, feature branches for fixes (e.g. fix/vision-bug)
- Python environment: virtual env recommended inside D:/AgentDesktopTest

---

## File Structure & Purpose

| File | Purpose | Status |
|---|---|---|
| main.py | Entry point. Initializes config, starts agent loop | Empty shell |
| agent_loop.py | Core autonomous goal loop. Drives all agent behavior | Empty shell |
| vision.py | Vision pipeline. Receives frames, analyzes content, returns structured data | Empty shell |
| screen_capture.py | Raw screen capture utility. Grabs screen or region as numpy array | Empty shell |
| ollama_client.py | Interface to local Ollama model. Sends prompts, receives responses | Empty shell |
| config.py | Global constants and settings. Imported by nearly everything | Empty shell |
| PROJECT_CONTEXT.md | This file. AI session map. Paste at top of every new session | Active |
| CONTRACTS.txt | Function signature contracts for all files. Paste at top of every new session | Skeleton only |
| README.md | Auto-generated GitHub readme | Default |

---

## Dependency Graph (import chain)

```
main.py
  imports: config.py, agent_loop.py

agent_loop.py
  imports: config.py, vision.py, ollama_client.py, screen_capture.py

vision.py
  imports: screen_capture.py

screen_capture.py
  imports: (none — base utility)

ollama_client.py
  imports: config.py

config.py
  imports: (none — base constants)
```

---

## Known Fragile Areas / Do Not Touch Rules
- config.py is imported by nearly every file. Any change to exported variable names WILL break ollama_client.py and agent_loop.py simultaneously.
- screen_capture.py return type must stay as np.ndarray. vision.py depends on this. Do not change to PIL.Image without updating vision.py.
- agent_loop.py is the only file that should call vision.py and ollama_client.py. Do not import these directly into main.py.
- Do not add new dependencies (pip packages) without noting them here under Dependencies.

---

## Dependencies (pip packages needed)
- To be filled in as files are built
- Expected: pillow, numpy, pyautogui or mss (screen capture), requests (ollama API)

---

## AI Session Rules (read before every coding session)
1. Always paste this file AND CONTRACTS.txt at the start of a session before requesting any code changes.
2. Only fix files explicitly mentioned. Do not touch other files unless asked.
3. State which branch you are working on at session start.
4. After every fix, output only the changed lines in diff format (+/-), not the full file.
5. Before writing any new file, confirm it against CONTRACTS.txt.
6. If asked to fix a bug, first explain what causes it and what else could break, THEN write the fix.
7. One file per session when possible. Never write two interdependent files in the same session.

---

## Changelog
| Date | Change | Files Affected |
|---|---|---|
| 2026-03-01 | Initial repo created on GitHub. All base files created as empty shells with header comments. | All files |
