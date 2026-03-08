# PROJECT_CONTEXT.md

## CURRENT STATE
- Branch: fix/runtime-baseline-01
- Phase: GUI/provider clarity + dependency-status caching pass complete
- GUI: main.py launches the Tk desktop GUI by default; shell_main.py is fallback if GUI import/launch fails
- Python baseline: main.py targets Python 3.11 specifically, probes for it, rebuilds `.venv` with it when needed, and refuses to silently continue on an unsupported interpreter
- Venv bootstrap: main.py auto-creates `.venv`, relaunches itself inside that environment, installs base requirements into it, verifies core runtime imports, and then runs provider bootstrap there
- Base deps: requirements.txt now includes the app’s current screen-capture and vision stack plus a setuptools range that preserves pkg_resources compatibility for Open Interpreter
- Failure visibility: startup prints captured stdout/stderr for install steps and pauses on startup failure so the console does not disappear before the error can be read
- Core dependency verification: bootstrap checks real import targets used by the app and auto-installs any missing packages before GUI import
- Provider bootstrap: provider readiness now verifies importability, not just package presence, so Open Interpreter is no longer marked ready when its import chain is broken
- Dependency-status caching: repeated GUI/monitor refreshes now reuse cached provider readiness state instead of re-running bootstrap probes every refresh cycle
- Requests compatibility: bootstrap repairs the requests stack when an incompatible chardet major version is introduced by downstream installs
- Vision runtime: EasyOCR reader initialization is lazy and falls back to CPU mode if GPU initialization is unavailable or incompatible
- Agent-S mapping: repo install target is `git+https://github.com/simular-ai/Agent-S.git` and the tracked import module is `gui_agents.s3`
- Settings: persisted to agent_settings.json and applied immediately across runtime/model-facing modules
- Startup: GUI boot initializes bootstrap checks, controller services, provider readiness, backend warmup, and monitor services automatically when enabled
- Tool providers: both open_interpreter and agents2_s3 have persisted enable flags, auto-install flags, preferred-provider selection, and startup readiness checks
- Routing: task execution distinguishes planner-only tasks from executable command tasks, with automatic route selection metadata and safe execution fallback behavior
- Vision: screen capture is adaptive so visual capture is requested only for observe/verify or explicitly visual work; cached state is reused for non-visual tasks
- Surfaces: GUI, monitor, shell fallback, and docs now all expose provider, route, preferred-provider, enabled-tool, and available-tool state consistently
- Shutdown: controller shutdown stops runtime + monitor cleanly
- Goal: real application behavior instead of a loose collection of scripts

## CHANGELOG
### [2026-03-08 12:38 EST] — GUI Provider Clarity + Dependency Cache Pass
- Added caching to bootstrap provider-status checks so repeated GUI and monitor refreshes do not keep re-running full dependency probes and spamming the console
- Updated runtime_controller.py so dependency refresh is forced only when tool-related settings change, not on every ordinary GUI setting update or warmup call
- Updated runtime_controller.py to expose preferred provider, enabled tools, and available tools alongside the active provider in dashboard and runtime payloads
- Updated gui_app.py to show Agent-S by name throughout the GUI instead of only the internal `agents2_s3` label
- Updated gui_app.py to relabel the single-provider selector as Preferred Tool Provider and surface enabled + available tools together in header, dashboard, run view, and settings
- Added GUI tool presets for Enable Both, Open Interpreter Only, and Agent-S Only so multi-tool configuration is obvious instead of hidden behind separate toggles

### [2026-03-08 12:29 EST] — Open Interpreter Importability + pkg_resources Compatibility Pass
- Added `setuptools>=68,<81` to requirements.txt so pkg_resources remains available for the current Open Interpreter import path
- Updated main.py packaging-tool bootstrap to stop upgrading setuptools past the compatible range during environment preparation
- Updated bootstrap.py core dependency verification to treat `pkg_resources` as a required runtime dependency and repair it automatically when missing
- Updated bootstrap.py provider readiness checks so Open Interpreter and Agent-S must be importable, not merely present on disk, before startup reports them as ready
- Updated agent_loop.py to surface the real Open Interpreter import failure instead of masking it behind a generic manual-install message

### [2026-03-08 12:26 EST] — Screen-Capture Dependency Closure Pass
- Confirmed screen_capture.py imports both numpy and mss directly
- Added `mss` to requirements.txt so base environment setup includes the real screen-capture dependency
- Added `mss` to bootstrap core dependency verification so startup auto-installs it if missing before GUI import
- Closed the gap between the screen-capture import chain and the declared base dependency set

### [2026-03-08 12:20 EST] — Core Runtime Dependency Verification + Vision Compatibility Pass
- Updated requirements.txt so the base environment includes the app's actual vision imports: numpy, opencv-python, and easyocr
- Updated bootstrap.py with core runtime dependency verification that checks and auto-installs real import targets before GUI startup
- Updated bootstrap.py to repair the requests stack when downstream installs introduce an incompatible chardet major version
- Updated vision.py so EasyOCR initialization is lazy and can fall back to CPU mode when GPU OCR startup is unavailable
- Updated main.py so core dependency verification runs before provider bootstrap completes startup handoff to the GUI

### [2026-03-08 12:09 EST] — Agent-S Repo-Backed Provider Install Pass
- Confirmed the simular-ai/Agent-S repository contains a Python setup.py package definition with package name `gui-agents`
- Confirmed the repository exposes an Agent-S console entry point through `gui_agents.s3.cli_app:main`
- Updated config.py so the agents2_s3 provider now defaults to `git+https://github.com/simular-ai/Agent-S.git` and normalizes legacy placeholder values to that repo-backed install target
- Updated config.py so the tracked module for Agent-S readiness is now `gui_agents.s3`
- Kept bootstrap.py repo-install compatible so startup auto-install can install directly from the Agent-S GitHub repository inside the project venv

### [2026-03-08 12:04 EST] — Python 3.11 Baseline + Missing Numpy + Provider Install Guard Pass
- Updated main.py to require Python 3.11, probe for a usable 3.11 interpreter, rebuild `.venv` with it when necessary, and relaunch into that runtime
- Added numpy to requirements.txt so vision.py imports successfully during first-run startup
- Updated bootstrap.py so open-interpreter auto-install explains Python 3.10-3.12 compatibility expectations instead of failing opaquely on unsupported runtimes
- Updated config.py and bootstrap.py so agents2-s3 no longer pretends a placeholder `agents2-s3` package name is a valid install target; it now expects a real pip package or git+ repo URL

### [2026-03-08 11:59 EST] — Startup Failure Visibility + Provider Package Separation Pass
- Updated main.py to capture and print stdout/stderr from package install steps instead of failing silently
- Updated main.py to pause on startup failure so double-click launches do not instantly close before the error can be read
- Removed provider packages from requirements.txt so open-interpreter and agents2-s3 are handled by provider bootstrap instead of base requirements install
- Reduced the chance of early startup failure during the first environment preparation pass

### [2026-03-08 11:53 EST] — Entrypoint Venv Bootstrap + Launch Visibility Pass
- Updated main.py to auto-create a local `.venv`, relaunch the app inside it, and install requirements into that environment before runtime bootstrap
- Updated main.py startup output so double-click or direct launch no longer appears as a silent blank console during long startup work
- Updated bootstrap.py install reporting so provider installs show visible progress and confirm the active Python executable
- Kept provider auto-installs inside the project virtual environment so open-interpreter and agents2-s3 land in the same runtime used by the app

### [2026-03-08 11:44 EST] — Final Full-Surface Polish Pass
- Updated gui_app.py to expose AUTO_TOOL_SELECTION and ADAPTIVE_VISION as live GUI toggles
- Updated gui_app.py dashboard and run views to surface provider, route, route reason, and vision reason
- Updated monitor.py to include route and vision-efficiency state in compact dashboard payloads
- Updated shell_main.py so fallback shell shows provider readiness, route decisions, and richer JSON status output
- Expanded README.md so the repo-level docs reflect the real runtime behavior instead of only the boot path

### [2026-03-08 11:40 EST] — Adaptive Routing + Vision Efficiency Pass
- Added AUTO_TOOL_SELECTION and ADAPTIVE_VISION persisted settings in config.py
- Updated agent_loop.py to classify task complexity, choose planner vs executable routing automatically, and avoid screen capture when cached state is sufficient
- Planner-only tasks now use the model adapter directly instead of Open Interpreter so command-capable execution is reserved for steps that actually need it
- Higher-complexity tasks can be tagged for agents2-s3-style orchestration while keeping safe Open Interpreter execution fallback in the current runtime
- Updated runtime_controller.py to surface auto-routing and vision-efficiency state in controller results

### [2026-03-08 11:35 EST] — Final Boot + Provider Pass
- Added bootstrap.py for startup dependency verification and optional pip auto-install of open-interpreter and agents2-s3
- Added persistent settings for provider selection, enable toggles, and per-provider auto-install behavior
- Updated main.py so dependency bootstrap runs before GUI import
- Updated gui_app.py so provider settings are visible and editable in the GUI
- Updated runtime_controller.py so startup reports provider readiness and active provider
- Updated agent_loop.py so runtime metadata includes provider selection and startup dependency checks
- Added requirements.txt with core and provider packages
- Expanded README.md with file linkage and provider/bootstrap notes

### [2026-03-08 11:33 EST] — Adapter + Client Compatibility Pass
- Simplified model_adapter.generate_text() so it always routes through generate_reply(), keeping timeout and explicit model selection behavior consistent
- Added explicit stream=False during Ollama warmup/generate preload calls
- Expanded query_model() to accept model_name and timeout so adapter and future callers can use one consistent call shape
- Added requested-model validation in query_model_reply() to avoid empty model edge cases

### [2026-03-08 11:27 EST] — GUI Application Polish Pass
- Added fallback shell_main.py so the app still runs if GUI launch fails
- Centralized startup services in runtime_controller.apply_all_startup_services()
- Centralized shutdown behavior in runtime_controller.shutdown()
- Polished gui_app.py to use controller-managed startup/shutdown instead of splitting lifecycle across files
- Ensured settings file is created on first launch and remains the single persisted configuration source
- Kept immediate-save behavior for numeric, toggle, and select settings
