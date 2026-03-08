from __future__ import annotations

import threading
import tkinter as tk
from tkinter import messagebox, ttk
from tkinter.scrolledtext import ScrolledText

from runtime_controller import build_runtime_controller


class AgentDesktopGUI(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.controller = build_runtime_controller()
        self._suspend_setting_events = False
        self._setting_jobs: dict[str, str] = {}
        self._refresh_job: str | None = None
        self._run_thread: threading.Thread | None = None

        self.title("AgentDesktopTest")
        self.geometry("1500x940")
        self.minsize(1280, 820)
        self.configure(bg="#0b1220")
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self._colors = {
            "bg": "#0b1220",
            "panel": "#111827",
            "panel_alt": "#162033",
            "text": "#e5e7eb",
            "muted": "#93a3b8",
            "accent": "#38bdf8",
        }

        self.summary_var = tk.StringVar(value="Initializing GUI...")
        self.settings_status_var = tk.StringVar(value="Settings save and apply automatically.")
        self.monitor_state_var = tk.StringVar(value="Monitor: unknown")
        self.footer_var = tk.StringVar(value="Ready")
        self.metric_vars = {k: tk.StringVar(value="--") for k in ["backend", "model", "runtime", "goal", "queue", "cpu", "ram", "gpu", "flags"]}

        self.setting_vars: dict[str, tk.Variable] = {}
        self.region_vars: dict[str, tk.StringVar] = {}

        self._configure_style()
        self._build_layout()
        self._load_settings_into_form()
        self._startup_runtime_services()
        self._refresh_all()
        self._schedule_refresh()

    def _configure_style(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure(".", background=self._colors["bg"], foreground=self._colors["text"], fieldbackground=self._colors["panel_alt"])
        style.configure("App.TFrame", background=self._colors["bg"])
        style.configure("Panel.TFrame", background=self._colors["panel"])
        style.configure("Card.TLabelframe", background=self._colors["panel"], foreground=self._colors["text"])
        style.configure("Card.TLabelframe.Label", background=self._colors["panel"], foreground=self._colors["text"], font=("Segoe UI", 11, "bold"))
        style.configure("Title.TLabel", background=self._colors["bg"], foreground=self._colors["text"], font=("Segoe UI", 20, "bold"))
        style.configure("Sub.TLabel", background=self._colors["bg"], foreground=self._colors["muted"], font=("Segoe UI", 10))
        style.configure("MetricKey.TLabel", background=self._colors["panel"], foreground=self._colors["muted"], font=("Segoe UI", 9, "bold"))
        style.configure("MetricValue.TLabel", background=self._colors["panel"], foreground=self._colors["text"], font=("Segoe UI", 12, "bold"))
        style.configure("TNotebook", background=self._colors["bg"], borderwidth=0)
        style.configure("TNotebook.Tab", background=self._colors["panel_alt"], foreground=self._colors["text"], padding=(16, 8))
        style.map("TNotebook.Tab", background=[("selected", self._colors["panel"])], foreground=[("selected", self._colors["accent"])])
        style.configure("Treeview", background=self._colors["panel_alt"], fieldbackground=self._colors["panel_alt"], foreground=self._colors["text"])
        style.configure("Treeview.Heading", background=self._colors["panel"], foreground=self._colors["text"])

    def _build_layout(self) -> None:
        root = ttk.Frame(self, style="App.TFrame", padding=16)
        root.pack(fill="both", expand=True)
        root.columnconfigure(0, weight=1)
        root.rowconfigure(1, weight=1)

        header = ttk.Frame(root, style="App.TFrame")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 14))
        header.columnconfigure(0, weight=1)

        ttk.Label(header, text="AgentDesktopTest", style="Title.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(header, text="Controller-backed desktop UI with live settings and health status.", style="Sub.TLabel").grid(row=1, column=0, sticky="w")
        ttk.Label(header, textvariable=self.summary_var, style="Sub.TLabel").grid(row=2, column=0, sticky="w")

        action_bar = ttk.Frame(header, style="App.TFrame")
        action_bar.grid(row=0, column=1, rowspan=3, sticky="e")
        ttk.Button(action_bar, text="Run Goal", command=self._run_goal_from_editor).grid(row=0, column=0, padx=4)
        ttk.Button(action_bar, text="Stop", command=self._stop_runtime).grid(row=0, column=1, padx=4)
        ttk.Button(action_bar, text="Refresh", command=self._refresh_all).grid(row=0, column=2, padx=4)
        ttk.Button(action_bar, text="Warm Up", command=self._warmup_model).grid(row=0, column=3, padx=4)

        notebook = ttk.Notebook(root)
        notebook.grid(row=1, column=0, sticky="nsew")

        self.dashboard_tab = ttk.Frame(notebook, style="Panel.TFrame", padding=14)
        self.run_tab = ttk.Frame(notebook, style="Panel.TFrame", padding=14)
        self.settings_tab = ttk.Frame(notebook, style="Panel.TFrame", padding=14)

        notebook.add(self.dashboard_tab, text="Dashboard")
        notebook.add(self.run_tab, text="Run")
        notebook.add(self.settings_tab, text="Settings")

        self._build_dashboard_tab()
        self._build_run_tab()
        self._build_settings_tab()

        footer = ttk.Frame(root, style="App.TFrame")
        footer.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        footer.columnconfigure(0, weight=1)
        ttk.Label(footer, textvariable=self.footer_var, style="Sub.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(footer, textvariable=self.settings_status_var, style="Sub.TLabel").grid(row=0, column=1, sticky="e")

    def _build_metric_card(self, parent, title: str, variable: tk.StringVar, row: int, column: int) -> None:
        card = ttk.Frame(parent, style="Panel.TFrame", padding=12)
        card.grid(row=row, column=column, sticky="nsew", padx=6, pady=6)
        ttk.Label(card, text=title, style="MetricKey.TLabel").pack(anchor="w")
        ttk.Label(card, textvariable=variable, style="MetricValue.TLabel", wraplength=360, justify="left").pack(anchor="w", pady=(6, 0))

    def _build_dashboard_tab(self) -> None:
        for col in range(3):
            self.dashboard_tab.columnconfigure(col, weight=1)

        metric_order = [["backend", "model", "runtime"], ["goal", "queue", "flags"], ["cpu", "ram", "gpu"]]
        for row, items in enumerate(metric_order):
            for col, key in enumerate(items):
                self._build_metric_card(self.dashboard_tab, key.title(), self.metric_vars[key], row, col)

        lower = ttk.Frame(self.dashboard_tab, style="Panel.TFrame")
        lower.grid(row=3, column=0, columnspan=3, sticky="nsew", pady=(14, 0))
        lower.columnconfigure(0, weight=2)
        lower.columnconfigure(1, weight=1)

        screen_frame = ttk.LabelFrame(lower, text="Latest Screen", style="Card.TLabelframe", padding=12)
        screen_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        self.screen_text = ScrolledText(screen_frame, height=12, bg=self._colors["panel_alt"], fg=self._colors["text"], insertbackground=self._colors["text"], relief="flat", wrap="word")
        self.screen_text.pack(fill="both", expand=True)

        health_frame = ttk.LabelFrame(lower, text="Health", style="Card.TLabelframe", padding=12)
        health_frame.grid(row=0, column=1, sticky="nsew")
        ttk.Label(health_frame, textvariable=self.monitor_state_var, style="Sub.TLabel").pack(anchor="w")
        self.health_text = ScrolledText(health_frame, height=12, bg=self._colors["panel_alt"], fg=self._colors["text"], insertbackground=self._colors["text"], relief="flat", wrap="word")
        self.health_text.pack(fill="both", expand=True, pady=(8, 0))

    def _build_run_tab(self) -> None:
        self.run_tab.columnconfigure(0, weight=1)
        self.run_tab.columnconfigure(1, weight=1)
        self.run_tab.rowconfigure(1, weight=1)

        top = ttk.LabelFrame(self.run_tab, text="Goal Runner", style="Card.TLabelframe", padding=12)
        top.grid(row=0, column=0, columnspan=2, sticky="ew")
        self.goal_text = ScrolledText(top, height=5, bg=self._colors["panel_alt"], fg=self._colors["text"], insertbackground=self._colors["text"], relief="flat", wrap="word")
        self.goal_text.pack(fill="x", expand=True)

        run_actions = ttk.Frame(top, style="Panel.TFrame")
        run_actions.pack(anchor="w", pady=(8, 0))
        ttk.Button(run_actions, text="Run Goal", command=self._run_goal_from_editor).pack(side="left", padx=(0, 6))
        ttk.Button(run_actions, text="Stop Runtime", command=self._stop_runtime).pack(side="left", padx=6)
        ttk.Button(run_actions, text="Refresh Runtime", command=self._refresh_runtime_panels).pack(side="left", padx=6)

        session_frame = ttk.LabelFrame(self.run_tab, text="Session Snapshot", style="Card.TLabelframe", padding=12)
        session_frame.grid(row=1, column=0, sticky="nsew", padx=(0, 8), pady=(12, 0))
        self.session_text = ScrolledText(session_frame, bg=self._colors["panel_alt"], fg=self._colors["text"], insertbackground=self._colors["text"], relief="flat", wrap="word")
        self.session_text.pack(fill="both", expand=True)

        right = ttk.Frame(self.run_tab, style="Panel.TFrame")
        right.grid(row=1, column=1, sticky="nsew", pady=(12, 0))
        right.columnconfigure(0, weight=1)
        right.rowconfigure(0, weight=1)
        right.rowconfigure(1, weight=1)

        queue_frame = ttk.LabelFrame(right, text="Pending Queue", style="Card.TLabelframe", padding=12)
        queue_frame.grid(row=0, column=0, sticky="nsew", pady=(0, 8))
        self.queue_tree = ttk.Treeview(queue_frame, columns=("kind", "priority", "status", "title"), show="headings", height=8)
        for col, width in [("kind", 120), ("priority", 90), ("status", 110), ("title", 420)]:
            self.queue_tree.heading(col, text=col.title())
            self.queue_tree.column(col, width=width, anchor="w")
        self.queue_tree.pack(fill="both", expand=True)

        notes_frame = ttk.LabelFrame(right, text="Recent Notes", style="Card.TLabelframe", padding=12)
        notes_frame.grid(row=1, column=0, sticky="nsew")
        self.notes_text = ScrolledText(notes_frame, bg=self._colors["panel_alt"], fg=self._colors["text"], insertbackground=self._colors["text"], relief="flat", wrap="word")
        self.notes_text.pack(fill="both", expand=True)

    def _build_settings_tab(self) -> None:
        outer = ttk.Frame(self.settings_tab, style="Panel.TFrame")
        outer.pack(fill="both", expand=True)
        outer.rowconfigure(0, weight=1)
        outer.columnconfigure(0, weight=1)

        canvas = tk.Canvas(outer, bg=self._colors["panel"], highlightthickness=0)
        scrollbar = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        body = ttk.Frame(canvas, style="Panel.TFrame")
        body.columnconfigure(0, weight=1)
        body.columnconfigure(1, weight=1)
        body.bind("<Configure>", lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=body, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")

        model_frame = ttk.LabelFrame(body, text="Model & Backend", style="Card.TLabelframe", padding=12)
        runtime_frame = ttk.LabelFrame(body, text="Runtime", style="Card.TLabelframe", padding=12)
        region_frame = ttk.LabelFrame(body, text="Screen Region", style="Card.TLabelframe", padding=12)
        app_frame = ttk.LabelFrame(body, text="Application", style="Card.TLabelframe", padding=12)
        tools_frame = ttk.LabelFrame(body, text="Tool Providers", style="Card.TLabelframe", padding=12)
        model_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 8), pady=(0, 8))
        runtime_frame.grid(row=0, column=1, sticky="nsew", pady=(0, 8))
        region_frame.grid(row=1, column=0, sticky="nsew", padx=(0, 8), pady=(0, 8))
        app_frame.grid(row=1, column=1, sticky="nsew", pady=(0, 8))
        tools_frame.grid(row=2, column=0, columnspan=2, sticky="nsew")
        for frame in [model_frame, runtime_frame, region_frame, app_frame, tools_frame]:
            frame.columnconfigure(1, weight=1)

        self._add_text_setting(model_frame, 0, "MODEL_NAME", "Model Name", combo_values=["qwen2.5-coder:7b", "deepseek-r1:8b", "qwen2.5:7b", "llama3.1:8b", "codellama:7b"])
        self._add_text_setting(model_frame, 1, "OLLAMA_URL", "Backend URL")
        self._add_numeric_setting(model_frame, 2, "OLLAMA_NUM_GPU", "GPU Layers", int, 0, 999, 1)
        self._add_numeric_setting(model_frame, 3, "MAX_RETRIES", "Retry Count", int, 1, 10, 1)

        self._add_numeric_setting(runtime_frame, 0, "LOOP_DELAY", "Loop Delay (s)", float, 0.1, 60.0, 0.1)
        self._add_toggle_setting(runtime_frame, 1, "DEBUG", "Debug Logging")
        self._add_toggle_setting(runtime_frame, 2, "BLOCK_CPU_COMPUTE", "Block CPU Compute")
        self._add_toggle_setting(runtime_frame, 3, "AUTO_TOOL_SELECTION", "Automatic Tool Selection")
        self._add_toggle_setting(runtime_frame, 4, "ADAPTIVE_VISION", "Adaptive Vision Capture")

        self._add_region_setting(region_frame, 0, "top", "Top")
        self._add_region_setting(region_frame, 1, "left", "Left")
        self._add_region_setting(region_frame, 2, "width", "Width")
        self._add_region_setting(region_frame, 3, "height", "Height")

        self._add_numeric_setting(app_frame, 0, "GUI_REFRESH_MS", "Refresh Interval (ms)", int, 500, 10000, 100)
        self._add_toggle_setting(app_frame, 1, "START_MONITOR_ON_GUI", "Run Monitor With GUI")
        self._add_toggle_setting(app_frame, 2, "AUTO_INSTALL_DEPENDENCIES", "Auto Install Missing Dependencies")

        self._add_text_setting(tools_frame, 0, "ACTIVE_TOOL_PROVIDER", "Active Tool Provider", combo_values=["open_interpreter", "agents2_s3"])
        self._add_toggle_setting(tools_frame, 1, "ENABLE_OPEN_INTERPRETER_TOOLS", "Enable Open Interpreter Tools")
        self._add_toggle_setting(tools_frame, 2, "ENABLE_AGENTS2_S3_TOOLS", "Enable agents2-s3 Tools")
        self._add_toggle_setting(tools_frame, 3, "AUTO_INSTALL_OPEN_INTERPRETER", "Auto Install Open Interpreter")
        self._add_toggle_setting(tools_frame, 4, "AUTO_INSTALL_AGENTS2_S3", "Auto Install agents2-s3")
        self._add_text_setting(tools_frame, 5, "AGENTS2_S3_PIP_PACKAGE", "agents2-s3 Pip Package")
        self._add_text_setting(tools_frame, 6, "AGENTS2_S3_MODULE", "agents2-s3 Module Name")

    def _set_text_widget(self, widget: ScrolledText, content: str) -> None:
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", content)
        widget.configure(state="disabled")

    def _add_label(self, parent, row: int, text: str) -> None:
        ttk.Label(parent, text=text, style="Sub.TLabel").grid(row=row, column=0, sticky="w", padx=(0, 10), pady=6)

    def _add_text_setting(self, parent, row: int, key: str, label: str, combo_values: list[str] | None = None) -> None:
        self._add_label(parent, row, label)
        var = tk.StringVar()
        self.setting_vars[key] = var
        widget = ttk.Combobox(parent, textvariable=var, values=combo_values or []) if combo_values else ttk.Entry(parent, textvariable=var)
        widget.grid(row=row, column=1, sticky="ew", pady=6)
        if combo_values:
            widget.bind("<<ComboboxSelected>>", lambda _e, setting_key=key, setting_var=var: self._persist_text_setting(setting_key, setting_var.get()))
        widget.bind("<FocusOut>", lambda _e, setting_key=key, setting_var=var: self._persist_text_setting(setting_key, setting_var.get()))
        widget.bind("<Return>", lambda _e, setting_key=key, setting_var=var: self._persist_text_setting(setting_key, setting_var.get()))

    def _add_numeric_setting(self, parent, row: int, key: str, label: str, caster, start, end, increment) -> None:
        self._add_label(parent, row, label)
        var = tk.StringVar()
        self.setting_vars[key] = var
        ttk.Spinbox(parent, textvariable=var, from_=start, to=end, increment=increment).grid(row=row, column=1, sticky="ew", pady=6)
        var.trace_add("write", lambda *_args, setting_key=key, setting_var=var, cast=caster: self._schedule_numeric_save(setting_key, setting_var, cast))

    def _add_region_setting(self, parent, row: int, field: str, label: str) -> None:
        self._add_label(parent, row, label)
        var = tk.StringVar()
        self.region_vars[field] = var
        ttk.Spinbox(parent, textvariable=var, from_=-99999, to=99999, increment=1).grid(row=row, column=1, sticky="ew", pady=6)
        var.trace_add("write", lambda *_args, region_field=field, region_var=var: self._schedule_region_save(region_field, region_var))

    def _add_toggle_setting(self, parent, row: int, key: str, label: str) -> None:
        var = tk.BooleanVar()
        self.setting_vars[key] = var
        ttk.Checkbutton(parent, text=label, variable=var).grid(row=row, column=0, columnspan=2, sticky="w", pady=6)
        var.trace_add("write", lambda *_args, setting_key=key, setting_var=var: self._persist_toggle_setting(setting_key, bool(setting_var.get())))

    def _load_settings_into_form(self) -> None:
        self._suspend_setting_events = True
        settings = self.controller.get_settings()
        try:
            for key, var in self.setting_vars.items():
                var.set(settings[key])
            for field, var in self.region_vars.items():
                var.set(settings["SCREEN_REGION"][field])
        finally:
            self._suspend_setting_events = False
        self.settings_status_var.set("Loaded saved settings.")

    def _startup_runtime_services(self) -> None:
        result = self.controller.apply_all_startup_services()
        deps = result.get("dependency_status", {})
        active_provider = deps.get("active_provider", result.get("tool_provider", "unknown"))
        self.monitor_state_var.set(f"Monitor: {'running' if result.get('monitoring') else 'stopped'}")
        self.summary_var.set(
            f"Backend {'ready' if result['backend_reachable'] else 'offline'} at {result['backend_url']} | model {result['model_name']} | provider {active_provider} | auto-route={'on' if result.get('auto_tool_selection') else 'off'} | adaptive-vision={'on' if result.get('adaptive_vision') else 'off'}"
        )
        self.footer_var.set(f"GUI started. Active tool provider: {active_provider}")
        if not result["backend_reachable"]:
            messagebox.showwarning("Backend Offline", f"The backend is not reachable at {result['backend_url']}. Settings still save immediately.")

    def _refresh_all(self) -> None:
        self._refresh_dashboard()
        self._refresh_runtime_panels()

    def _refresh_dashboard(self) -> None:
        status = self.controller.get_dashboard_status()
        settings = self.controller.get_settings()
        goal_text = status.get("goal") or self.controller.get_current_goal() or "(no goal set)"
        flags = status.get("health_flags", [])
        provider = status.get("tool_provider", settings["ACTIVE_TOOL_PROVIDER"])
        route = status.get("last_route", "") or "(none)"
        self.metric_vars["backend"].set("online" if status.get("backend_reachable") else "offline")
        self.metric_vars["model"].set(settings["MODEL_NAME"])
        self.metric_vars["runtime"].set(f"{status.get('runtime_status', 'unknown')} | {provider} | {route}")
        self.metric_vars["goal"].set(goal_text)
        self.metric_vars["queue"].set(f"pending {status.get('pending_task_count', 0)} | done {status.get('completed_task_count', 0)} | failed {status.get('failed_task_count', 0)}")
        self.metric_vars["cpu"].set(f"{status.get('cpu_percent')}%")
        self.metric_vars["ram"].set(f"{status.get('ram_percent')}%")
        gpu_util = status.get("gpu_utilization_percent")
        gpu_temp = status.get("gpu_temperature_c")
        self.metric_vars["gpu"].set(f"util {gpu_util}% | temp {gpu_temp}C" if gpu_util is not None else "unavailable")
        self.metric_vars["flags"].set(", ".join(flags) if flags else "healthy")
        self.monitor_state_var.set(f"Monitor: {'running' if self.controller.is_monitoring() else 'stopped'}")
        self.summary_var.set(status.get("summary", "System ready"))
        self.footer_var.set(
            f"Refresh interval: {settings['GUI_REFRESH_MS']} ms | provider: {provider} | auto-route: {'on' if settings['AUTO_TOOL_SELECTION'] else 'off'} | adaptive-vision: {'on' if settings['ADAPTIVE_VISION'] else 'off'}"
        )
        self._set_text_widget(self.screen_text, status.get("last_screen_description", "No screen description available yet."))
        self._set_text_widget(
            self.health_text,
            "\n".join([
                f"Summary: {status.get('summary', '')}",
                f"Backend reachable: {status.get('backend_reachable', False)}",
                f"Model loaded: {status.get('model_loaded', False)}",
                f"Runtime running: {status.get('runtime_running', False)}",
                f"Active tool provider: {provider}",
                f"Last route: {status.get('last_route', '')}",
                f"Route reason: {status.get('last_route_reason', '')}",
                f"Vision reason: {status.get('last_vision_reason', '')}",
                f"Auto tool selection: {settings['AUTO_TOOL_SELECTION']}",
                f"Adaptive vision: {settings['ADAPTIVE_VISION']}",
                f"Flags: {', '.join(flags) if flags else 'none'}",
                f"Refresh interval: {settings['GUI_REFRESH_MS']} ms",
            ]),
        )

    def _refresh_runtime_panels(self) -> None:
        snapshot = self.controller.get_runtime_snapshot()
        self._set_text_widget(
            self.session_text,
            "\n".join([
                f"Active: {snapshot.get('active', False)}",
                f"Running: {snapshot.get('running', False)}",
                f"Session ID: {snapshot.get('session_id', '')}",
                f"Goal: {snapshot.get('goal', '')}",
                f"Status: {snapshot.get('status', '')}",
                f"Tool Provider: {snapshot.get('tool_provider', '')}",
                f"Last Route: {snapshot.get('last_route', '')}",
                f"Route Reason: {snapshot.get('last_route_reason', '')}",
                f"Vision Reason: {snapshot.get('last_vision_reason', '')}",
                f"Active Model: {snapshot.get('active_model', '')}",
                f"Planner Model: {snapshot.get('planner_model', '')}",
                f"Executor Model: {snapshot.get('executor_model', '')}",
                f"Pending Tasks: {snapshot.get('pending_task_count', 0)}",
                f"Completed Tasks: {snapshot.get('completed_task_count', 0)}",
                f"Failed Tasks: {snapshot.get('failed_task_count', 0)}",
                "",
                "Last Action:",
                snapshot.get('last_action', '') or '(none)',
            ]),
        )

        for item in self.queue_tree.get_children():
            self.queue_tree.delete(item)
        for task in snapshot.get("pending_tasks", []):
            self.queue_tree.insert("", "end", values=(task.get("kind", ""), task.get("priority", ""), task.get("status", ""), task.get("title", "")))

        notes = snapshot.get("notes", [])
        self._set_text_widget(self.notes_text, "\n".join(notes[-20:]) if notes else "No notes yet.")

    def _schedule_refresh(self) -> None:
        if self._refresh_job is not None:
            self.after_cancel(self._refresh_job)
        self._refresh_job = self.after(self.controller.get_settings().get("GUI_REFRESH_MS", 1500), self._auto_refresh)

    def _auto_refresh(self) -> None:
        self._refresh_job = None
        self._refresh_all()
        self._schedule_refresh()

    def _run_goal_from_editor(self) -> None:
        goal = self.goal_text.get("1.0", "end").strip()
        if not goal:
            messagebox.showinfo("Goal Required", "Enter a goal before starting the runtime.")
            return
        if self._run_thread and self._run_thread.is_alive():
            messagebox.showinfo("Already Running", "The runtime is already executing a goal.")
            return
        self.controller.set_goal(goal)
        self.summary_var.set(f"Running goal: {goal[:120]}")
        self.footer_var.set("Goal dispatched to runtime worker.")
        self._run_thread = threading.Thread(target=self._run_goal_worker, args=(goal,), daemon=True)
        self._run_thread.start()

    def _run_goal_worker(self, goal: str) -> None:
        try:
            snapshot = self.controller.run_goal(goal)
        except Exception as e:
            self.after(0, lambda: self._handle_run_error(str(e)))
            return
        self.after(0, lambda: self._handle_run_complete(snapshot))

    def _handle_run_error(self, message: str) -> None:
        self.summary_var.set(f"Run failed: {message}")
        self.footer_var.set("Runtime reported an error.")
        messagebox.showerror("Run Error", message)
        self._refresh_all()

    def _handle_run_complete(self, snapshot: dict) -> None:
        self.summary_var.set(f"Run finished with status: {snapshot.get('status', 'unknown')}")
        self.footer_var.set("Runtime finished processing the current goal.")
        self._refresh_all()

    def _stop_runtime(self) -> None:
        self.controller.stop_runtime()
        self.summary_var.set("Stop requested.")
        self.footer_var.set("Stop request sent to runtime.")
        self._refresh_all()

    def _warmup_model(self) -> None:
        def worker() -> None:
            result = self.controller.warmup_current_model()
            self.after(0, lambda: self._handle_warmup_result(result))

        self.summary_var.set("Warming up current model...")
        self.footer_var.set("Warmup started.")
        threading.Thread(target=worker, daemon=True).start()

    def _handle_warmup_result(self, result: dict) -> None:
        if result["backend_reachable"]:
            self.summary_var.set(f"Warmup {'ok' if result['warmup_ok'] else 'incomplete'} for {result['model_name']}")
            self.footer_var.set(f"Model warmup completed. Provider: {result.get('tool_provider', 'unknown')}")
        else:
            self.summary_var.set("Warmup failed because backend is offline.")
            self.footer_var.set("Warmup could not run because backend is offline.")
        self._refresh_all()

    def _schedule_setting_job(self, key: str, callback) -> None:
        if key in self._setting_jobs:
            self.after_cancel(self._setting_jobs[key])
        self._setting_jobs[key] = self.after(180, callback)

    def _schedule_numeric_save(self, key: str, var: tk.StringVar, caster) -> None:
        if self._suspend_setting_events:
            return
        raw = str(var.get()).strip()
        if raw in {"", "-", ".", "-."}:
            return
        try:
            caster(raw)
        except Exception:
            self.settings_status_var.set(f"Waiting for a valid numeric value for {key}.")
            return
        self._schedule_setting_job(key, lambda: self._persist_numeric_setting(key, raw, caster))

    def _schedule_region_save(self, field: str, var: tk.StringVar) -> None:
        if self._suspend_setting_events:
            return
        raw = str(var.get()).strip()
        if raw in {"", "-"}:
            return
        try:
            int(raw)
        except Exception:
            self.settings_status_var.set(f"Waiting for a valid screen region value for {field}.")
            return
        self._schedule_setting_job(f"SCREEN_REGION.{field}", lambda: self._persist_region_setting(field, raw))

    def _persist_numeric_setting(self, key: str, raw: str, caster) -> None:
        self._setting_jobs.pop(key, None)
        try:
            value = caster(raw)
            self.controller.update_setting(key, value)
            self.settings_status_var.set(f"Saved and applied {key} = {value}")
            if key == "GUI_REFRESH_MS":
                self._schedule_refresh()
            self._refresh_all()
        except Exception as e:
            self.settings_status_var.set(f"Could not save {key}: {e}")

    def _persist_region_setting(self, field: str, raw: str) -> None:
        self._setting_jobs.pop(f"SCREEN_REGION.{field}", None)
        try:
            value = int(raw)
            self.controller.update_screen_region_value(field, value)
            self.settings_status_var.set(f"Saved and applied SCREEN_REGION.{field} = {value}")
            self._refresh_all()
        except Exception as e:
            self.settings_status_var.set(f"Could not save screen region {field}: {e}")

    def _persist_toggle_setting(self, key: str, value: bool) -> None:
        if self._suspend_setting_events:
            return
        try:
            self.controller.update_setting(key, value)
            self.monitor_state_var.set(f"Monitor: {'running' if self.controller.is_monitoring() else 'stopped'}")
            self.settings_status_var.set(f"Saved and applied {key} = {value}")
            self._refresh_all()
        except Exception as e:
            self.settings_status_var.set(f"Could not save {key}: {e}")

    def _persist_text_setting(self, key: str, value: str) -> None:
        if self._suspend_setting_events:
            return
        cleaned = value.strip()
        if not cleaned:
            self.settings_status_var.set(f"{key} cannot be empty.")
            return
        try:
            self.controller.update_setting(key, cleaned)
            self.settings_status_var.set(f"Saved and applied {key} = {cleaned}")
            self._refresh_all()
        except Exception as e:
            self.settings_status_var.set(f"Could not save {key}: {e}")

    def _on_close(self) -> None:
        try:
            self.controller.shutdown()
        finally:
            if self._refresh_job is not None:
                self.after_cancel(self._refresh_job)
            self.destroy()



def main() -> None:
    app = AgentDesktopGUI()
    app.mainloop()


if __name__ == "__main__":
    main()
