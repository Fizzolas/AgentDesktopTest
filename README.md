# AgentDesktopTest

AgentDesktopTest now boots like a desktop application: `main.py` starts dependency bootstrap first, launches the Tk GUI by default, and falls back to `shell_main.py` if GUI startup fails.

## Linked files
- `main.py` — primary application entry point
- `gui_app.py` — desktop UI with live routing, provider, and vision settings
- `runtime_controller.py` — startup/shutdown/settings bridge
- `bootstrap.py` — auto-install and provider readiness checks
- `agent_loop.py` — runtime loop using planner-vs-executor routing, adaptive vision, and provider metadata
- `monitor.py` — health and runtime telemetry, including route and vision reasons
- `shell_main.py` — fallback shell with provider and route visibility
- `config.py` — persistent settings including tool-provider, auto-routing, and adaptive-vision options

## Tool providers
The app exposes saved settings for both `open_interpreter` and `agents2_s3`, including enable toggles, auto-install toggles, active-provider selection, and editable package/module names for agents2-s3.

## Execution efficiency
The runtime now prefers the lightest path that can finish the current task:
- planner-only tasks stay in the model adapter path
- executable desktop tasks route to the command-capable runtime path
- visual capture runs only when a task needs current UI confirmation, otherwise cached screen state is reused

## Auto install
If auto-install is enabled, startup checks for:
- `open-interpreter` via the `interpreter` module
- `agents2-s3` via the configured `AGENTS2_S3_MODULE` value

Those checks run through `bootstrap.py` before GUI import and again during controller startup so missing provider packages can be installed automatically when possible.
