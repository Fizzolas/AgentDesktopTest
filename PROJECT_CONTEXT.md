# PROJECT_CONTEXT.md

## CURRENT STATE
- Branch: fix/runtime-baseline-01
- Phase: final full-surface polish pass complete
- GUI: main.py launches the Tk desktop GUI by default; shell_main.py is fallback if GUI import/launch fails
- Settings: persisted to agent_settings.json and applied immediately across runtime/model-facing modules
- Startup: GUI boot initializes bootstrap checks, controller services, provider readiness, backend warmup, and monitor services automatically when enabled
- Tool providers: both open_interpreter and agents2_s3 have persisted enable flags, auto-install flags, active-provider selection, and startup readiness checks
- Routing: task execution distinguishes planner-only tasks from executable command tasks, with automatic route selection metadata and safe execution fallback behavior
- Vision: screen capture is adaptive so visual capture is requested only for observe/verify or explicitly visual work; cached state is reused for non-visual tasks
- Surfaces: GUI, monitor, shell fallback, and docs now all expose provider, route, and vision-efficiency state consistently
- Shutdown: controller shutdown stops runtime + monitor cleanly
- Goal: real application behavior instead of a loose collection of scripts

## CHANGELOG
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
