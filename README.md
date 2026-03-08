# AgentDesktopTest

AgentDesktopTest now boots like a desktop application: `main.py` starts dependency bootstrap first, launches the Tk GUI by default, and falls back to `shell_main.py` if GUI startup fails.

## Linked files
- `main.py` — primary application entry point
- `gui_app.py` — desktop UI
- `runtime_controller.py` — startup/shutdown/settings bridge
- `bootstrap.py` — auto-install and provider readiness checks
- `agent_loop.py` — runtime loop using Open Interpreter today, with provider selection metadata for Open Interpreter and agents2-s3
- `config.py` — persistent settings including tool-provider options

## Tool providers
The app now exposes saved settings for both `open_interpreter` and `agents2_s3`, including enable toggles, auto-install toggles, active provider selection, and editable package/module names for agents2-s3.

## Auto install
If auto-install is enabled, startup checks for:
- `open-interpreter` via the `interpreter` module
- `agents2-s3` via the configured `AGENTS2_S3_MODULE` value

Those checks run through `bootstrap.py` before GUI import and again during controller startup so missing provider packages can be installed automatically when possible.
