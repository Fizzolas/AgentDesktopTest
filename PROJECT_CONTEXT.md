# PROJECT_CONTEXT.md

## CURRENT STATE
- Branch: fix/runtime-baseline-01
- Phase: adapter/client compatibility pass complete
- GUI: main.py launches the Tk desktop GUI by default; shell_main.py is fallback if GUI import/launch fails
- Settings: persisted to agent_settings.json and applied immediately across runtime/model-facing modules
- Startup: GUI boot initializes the controller, warms the backend when reachable, and starts monitor services automatically when enabled
- Shutdown: controller shutdown stops runtime + monitor cleanly
- Goal: real application behavior instead of a loose collection of scripts

## CHANGELOG
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
