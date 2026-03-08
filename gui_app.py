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
        self._suspend = False
        self._jobs = {}
        self._refresh_job = None
        self._runner = None
        self.title("AgentDesktopTest")
        self.geometry("1500x940")
        self.minsize(1280, 820)
        self.configure(bg="#0b1220")
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._style()
        self.summary = tk.StringVar(value="Initializing GUI...")
        self.settings_status = tk.StringVar(value="Settings save and apply automatically.")
        self.monitor_state = tk.StringVar(value="Monitor: unknown")
        self.metrics = {k: tk.StringVar(value="--") for k in ["backend","model","runtime","goal","queue","cpu","ram","gpu","flags"]}
        self.setting_vars, self.region_vars = {}, {}
        self._build()
        self._load_form()
        self._startup()
        self.refresh_all()
        self._schedule_refresh()

    def _style(self):
        s = ttk.Style(self); s.theme_use("clam")
        self.c = {"bg":"#0b1220","panel":"#111827","field":"#162033","fg":"#e5e7eb","muted":"#93a3b8","accent":"#38bdf8"}
        s.configure(".", background=self.c["bg"], foreground=self.c["fg"], fieldbackground=self.c["field"])
        s.configure("App.TFrame", background=self.c["bg"])
        s.configure("Panel.TFrame", background=self.c["panel"])
        s.configure("Card.TLabelframe", background=self.c["panel"], foreground=self.c["fg"])
        s.configure("Card.TLabelframe.Label", background=self.c["panel"], foreground=self.c["fg"], font=("Segoe UI",11,"bold"))
        s.configure("Title.TLabel", background=self.c["bg"], foreground=self.c["fg"], font=("Segoe UI",20,"bold"))
        s.configure("Sub.TLabel", background=self.c["bg"], foreground=self.c["muted"], font=("Segoe UI",10))
        s.configure("MetricK.TLabel", background=self.c["panel"], foreground=self.c["muted"], font=("Segoe UI",9,"bold"))
        s.configure("MetricV.TLabel", background=self.c["panel"], foreground=self.c["fg"], font=("Segoe UI",12,"bold"))
        s.configure("TNotebook", background=self.c["bg"], borderwidth=0)
        s.configure("TNotebook.Tab", background=self.c["field"], foreground=self.c["fg"], padding=(16,8))
        s.map("TNotebook.Tab", background=[("selected", self.c["panel"])], foreground=[("selected", self.c["accent"])])
        s.configure("Treeview", background=self.c["field"], fieldbackground=self.c["field"], foreground=self.c["fg"])
        s.configure("Treeview.Heading", background=self.c["panel"], foreground=self.c["fg"])

    def _build(self):
        root = ttk.Frame(self, style="App.TFrame", padding=16); root.pack(fill="both", expand=True); root.columnconfigure(0, weight=1); root.rowconfigure(1, weight=1)
        head = ttk.Frame(root, style="App.TFrame"); head.grid(row=0, column=0, sticky="ew", pady=(0,14)); head.columnconfigure(0, weight=1)
        ttk.Label(head, text="AgentDesktopTest", style="Title.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(head, text="In-depth GUI with live settings, runtime control, and health monitoring.", style="Sub.TLabel").grid(row=1, column=0, sticky="w")
        ttk.Label(head, textvariable=self.summary, style="Sub.TLabel").grid(row=2, column=0, sticky="w")
        actions = ttk.Frame(head, style="App.TFrame"); actions.grid(row=0, column=1, rowspan=3, sticky="e")
        ttk.Button(actions, text="Run Goal", command=self.run_goal).grid(row=0, column=0, padx=4)
        ttk.Button(actions, text="Stop", command=self.stop_goal).grid(row=0, column=1, padx=4)
        ttk.Button(actions, text="Refresh", command=self.refresh_all).grid(row=0, column=2, padx=4)
        ttk.Button(actions, text="Warm Up", command=self.warmup).grid(row=0, column=3, padx=4)
        nb = ttk.Notebook(root); nb.grid(row=1, column=0, sticky="nsew")
        self.tab_dash = ttk.Frame(nb, style="Panel.TFrame", padding=14)
        self.tab_run = ttk.Frame(nb, style="Panel.TFrame", padding=14)
        self.tab_set = ttk.Frame(nb, style="Panel.TFrame", padding=14)
        nb.add(self.tab_dash, text="Dashboard"); nb.add(self.tab_run, text="Run"); nb.add(self.tab_set, text="Settings")
        self._build_dash(); self._build_run(); self._build_settings()

    def _metric(self, parent, title, var, r, c):
        f = ttk.Frame(parent, style="Panel.TFrame", padding=12); f.grid(row=r, column=c, sticky="nsew", padx=6, pady=6)
        ttk.Label(f, text=title, style="MetricK.TLabel").pack(anchor="w")
        ttk.Label(f, textvariable=var, style="MetricV.TLabel", wraplength=360, justify="left").pack(anchor="w", pady=(6,0))

    def _build_dash(self):
        for i in range(3): self.tab_dash.columnconfigure(i, weight=1)
        for r, items in enumerate([["backend","model","runtime"],["goal","queue","flags"],["cpu","ram","gpu"]]):
            for c, k in enumerate(items): self._metric(self.tab_dash, k.title(), self.metrics[k], r, c)
        low = ttk.Frame(self.tab_dash, style="Panel.TFrame"); low.grid(row=3, column=0, columnspan=3, sticky="nsew", pady=(14,0)); low.columnconfigure(0, weight=2); low.columnconfigure(1, weight=1)
        a = ttk.LabelFrame(low, text="Latest Screen", style="Card.TLabelframe", padding=12); a.grid(row=0, column=0, sticky="nsew", padx=(0,8))
        b = ttk.LabelFrame(low, text="Health", style="Card.TLabelframe", padding=12); b.grid(row=0, column=1, sticky="nsew")
        self.screen = ScrolledText(a, height=12, bg=self.c["field"], fg=self.c["fg"], insertbackground=self.c["fg"], relief="flat", wrap="word"); self.screen.pack(fill="both", expand=True)
        ttk.Label(b, textvariable=self.monitor_state, style="Sub.TLabel").pack(anchor="w")
        self.health = ScrolledText(b, height=12, bg=self.c["field"], fg=self.c["fg"], insertbackground=self.c["fg"], relief="flat", wrap="word"); self.health.pack(fill="both", expand=True, pady=(8,0))

    def _build_run(self):
        self.tab_run.columnconfigure(0, weight=1); self.tab_run.columnconfigure(1, weight=1); self.tab_run.rowconfigure(1, weight=1)
        top = ttk.LabelFrame(self.tab_run, text="Goal Runner", style="Card.TLabelframe", padding=12); top.grid(row=0, column=0, columnspan=2, sticky="ew")
        self.goal = ScrolledText(top, height=5, bg=self.c["field"], fg=self.c["fg"], insertbackground=self.c["fg"], relief="flat", wrap="word"); self.goal.pack(fill="x", expand=True)
        btns = ttk.Frame(top, style="Panel.TFrame"); btns.pack(anchor="w", pady=(8,0))
        ttk.Button(btns, text="Run Goal", command=self.run_goal).pack(side="left", padx=(0,6))
        ttk.Button(btns, text="Stop Runtime", command=self.stop_goal).pack(side="left", padx=6)
        ttk.Button(btns, text="Refresh Runtime", command=self.refresh_runtime).pack(side="left", padx=6)
        left = ttk.LabelFrame(self.tab_run, text="Session Snapshot", style="Card.TLabelframe", padding=12); left.grid(row=1, column=0, sticky="nsew", padx=(0,8), pady=(12,0))
        self.session = ScrolledText(left, bg=self.c["field"], fg=self.c["fg"], insertbackground=self.c["fg"], relief="flat", wrap="word"); self.session.pack(fill="both", expand=True)
        right = ttk.Frame(self.tab_run, style="Panel.TFrame"); right.grid(row=1, column=1, sticky="nsew", pady=(12,0)); right.rowconfigure(0, weight=1); right.rowconfigure(1, weight=1); right.columnconfigure(0, weight=1)
        qf = ttk.LabelFrame(right, text="Pending Queue", style="Card.TLabelframe", padding=12); qf.grid(row=0, column=0, sticky="nsew", pady=(0,8))
        self.queue = ttk.Treeview(qf, columns=("kind","priority","status","title"), show="headings", height=8)
        for col, w in [("kind",120),("priority",90),("status",110),("title",420)]: self.queue.heading(col, text=col.title()); self.queue.column(col, width=w, anchor="w")
        self.queue.pack(fill="both", expand=True)
        nf = ttk.LabelFrame(right, text="Recent Notes", style="Card.TLabelframe", padding=12); nf.grid(row=1, column=0, sticky="nsew")
        self.notes = ScrolledText(nf, bg=self.c["field"], fg=self.c["fg"], insertbackground=self.c["fg"], relief="flat", wrap="word"); self.notes.pack(fill="both", expand=True)

    def _build_settings(self):
        outer = ttk.Frame(self.tab_set, style="Panel.TFrame"); outer.pack(fill="both", expand=True); outer.rowconfigure(0, weight=1); outer.columnconfigure(0, weight=1)
        can = tk.Canvas(outer, bg=self.c["panel"], highlightthickness=0); sc = ttk.Scrollbar(outer, orient="vertical", command=can.yview); body = ttk.Frame(can, style="Panel.TFrame"); self.set_body = body
        body.bind("<Configure>", lambda e: can.configure(scrollregion=can.bbox("all")))
        can.create_window((0,0), window=body, anchor="nw"); can.configure(yscrollcommand=sc.set)
        can.grid(row=0, column=0, sticky="nsew"); sc.grid(row=0, column=1, sticky="ns")
        body.columnconfigure(0, weight=1); body.columnconfigure(1, weight=1)
        model = ttk.LabelFrame(body, text="Model & Backend", style="Card.TLabelframe", padding=12); model.grid(row=0, column=0, sticky="nsew", padx=(0,8), pady=(0,8)); model.columnconfigure(1, weight=1)
        runtime = ttk.LabelFrame(body, text="Runtime", style="Card.TLabelframe", padding=12); runtime.grid(row=0, column=1, sticky="nsew", pady=(0,8)); runtime.columnconfigure(1, weight=1)
        region = ttk.LabelFrame(body, text="Screen Region", style="Card.TLabelframe", padding=12); region.grid(row=1, column=0, sticky="nsew", padx=(0,8)); region.columnconfigure(1, weight=1)
        app = ttk.LabelFrame(body, text="Application", style="Card.TLabelframe", padding=12); app.grid(row=1, column=1, sticky="nsew"); app.columnconfigure(1, weight=1)
        self._text_setting(model,0,"MODEL_NAME","Model Name",combo=["qwen2.5-coder:7b","deepseek-r1:8b","qwen2.5:7b","llama3.1:8b","codellama:7b"])
        self._text_setting(model,1,"OLLAMA_URL","Backend URL")
        self._num_setting(model,2,"OLLAMA_NUM_GPU","GPU Layers",int,0,999,1)
        self._num_setting(model,3,"MAX_RETRIES","Retry Count",int,1,10,1)
        self._num_setting(runtime,0,"LOOP_DELAY","Loop Delay (s)",float,0.1,60.0,0.1)
        self._toggle(runtime,1,"DEBUG","Debug Logging")
        self._toggle(runtime,2,"BLOCK_CPU_COMPUTE","Block CPU Compute")
        self._region(region,0,"top","Top"); self._region(region,1,"left","Left"); self._region(region,2,"width","Width"); self._region(region,3,"height","Height")
        self._num_setting(app,0,"GUI_REFRESH_MS","Refresh Interval (ms)",int,500,10000,100)
        self._toggle(app,1,"START_MONITOR_ON_GUI","Run Monitor With GUI")
        foot = ttk.Frame(outer, style="Panel.TFrame", padding=(0,8,0,0)); foot.grid(row=1, column=0, columnspan=2, sticky="ew"); foot.columnconfigure(0, weight=1)
        ttk.Label(foot, textvariable=self.settings_status, style="Sub.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Button(foot, text="Reload Saved Settings", command=self._load_form).grid(row=0, column=1, padx=4)
        ttk.Button(foot, text="Warm Up Current Model", command=self.warmup).grid(row=0, column=2, padx=4)

    def _row_label(self, parent, row, text):
        ttk.Label(parent, text=text, style="Sub.TLabel").grid(row=row, column=0, sticky="w", padx=(0,10), pady=6)

    def _text_setting(self, parent, row, key, label, combo=None):
        self._row_label(parent,row,label); v = tk.StringVar(); self.setting_vars[key] = v
        w = ttk.Combobox(parent, textvariable=v, values=combo or []) if combo else ttk.Entry(parent, textvariable=v)
        w.grid(row=row, column=1, sticky="ew", pady=6)
        if combo: w.bind("<<ComboboxSelected>>", lambda e, k=key, var=v: self._save_text(k, var.get()))
        w.bind("<FocusOut>", lambda e, k=key, var=v: self._save_text(k, var.get()))
        w.bind("<Return>", lambda e, k=key, var=v: self._save_text(k, var.get()))

    def _num_setting(self, parent, row, key, label, caster, a, b, inc):
        self._row_label(parent,row,label); v = tk.StringVar(); self.setting_vars[key] = v
        ttk.Spinbox(parent, textvariable=v, from_=a, to=b, increment=inc).grid(row=row, column=1, sticky="ew", pady=6)
        v.trace_add("write", lambda *_ , k=key, var=v, cast=caster: self._schedule_num(k, var, cast))

    def _region(self, parent, row, field, label):
        self._row_label(parent,row,label); v = tk.StringVar(); self.region_vars[field] = v
        ttk.Spinbox(parent, textvariable=v, from_=-99999, to=99999, increment=1).grid(row=row, column=1, sticky="ew", pady=6)
        v.trace_add("write", lambda *_ , f=field, var=v: self._schedule_region(f, var))

    def _toggle(self, parent, row, key, label):
        v = tk.BooleanVar(); self.setting_vars[key] = v
        ttk.Checkbutton(parent, text=label, variable=v).grid(row=row, column=0, columnspan=2, sticky="w", pady=6)
        v.trace_add("write", lambda *_ , k=key, var=v: self._save_toggle(k, bool(var.get())))

    def _load_form(self):
        self._suspend = True; s = self.controller.get_settings()
        try:
            for k, v in self.setting_vars.items(): v.set(s[k])
            for k, v in self.region_vars.items(): v.set(s["SCREEN_REGION"][k])
        finally:
            self._suspend = False
        self.settings_status.set("Loaded saved settings.")

    def _startup(self):
        r = self.controller.startup(); s = self.controller.get_settings()
        if s["START_MONITOR_ON_GUI"]: self.controller.start_monitoring()
        self.monitor_state.set(f"Monitor: {'running' if self.controller.is_monitoring() else 'stopped'}")
        self.summary.set(f"Backend {'ready' if r['backend_reachable'] else 'offline'} at {r['backend_url']} | model {r['model_name']} | warmup={'ok' if r['warmup_ok'] else 'pending'}")
        if not r["backend_reachable"]:
            messagebox.showwarning("Backend Offline", f"The backend is not reachable at {r['backend_url']}. Settings still save immediately.")

    def _set_text(self, w, txt):
        w.configure(state="normal"); w.delete("1.0","end"); w.insert("1.0", txt); w.configure(state="disabled")

    def refresh_all(self): self.refresh_dashboard(); self.refresh_runtime()

    def refresh_dashboard(self):
        st = self.controller.get_dashboard_status(); s = self.controller.get_settings(); flags = st.get("health_flags", [])
        self.metrics["backend"].set("online" if st.get("backend_reachable") else "offline")
        self.metrics["model"].set(s["MODEL_NAME"])
        self.metrics["runtime"].set(st.get("runtime_status", "unknown"))
        self.metrics["goal"].set(st.get("goal") or "(no goal set)")
        self.metrics["queue"].set(f"pending {st.get('pending_task_count',0)} | done {st.get('completed_task_count',0)} | failed {st.get('failed_task_count',0)}")
        self.metrics["cpu"].set(f"{st.get('cpu_percent')}%")
        self.metrics["ram"].set(f"{st.get('ram_percent')}%")
        gu, gt = st.get("gpu_utilization_percent"), st.get("gpu_temperature_c")
        self.metrics["gpu"].set(f"util {gu}% | temp {gt}C" if gu is not None else "unavailable")
        self.metrics["flags"].set(", ".join(flags) if flags else "healthy")
        self.monitor_state.set(f"Monitor: {'running' if self.controller.is_monitoring() else 'stopped'}")
        self.summary.set(st.get("summary", "System ready"))
        self._set_text(self.screen, st.get("last_screen_description", "No screen description available yet."))
        self._set_text(self.health, "\n".join([f"Summary: {st.get('summary','')}", f"Backend reachable: {st.get('backend_reachable',False)}", f"Model loaded: {st.get('model_loaded',False)}", f"Runtime running: {st.get('runtime_running',False)}", f"Flags: {', '.join(flags) if flags else 'none'}", f"Refresh interval: {s.get('GUI_REFRESH_MS')} ms"]))

    def refresh_runtime(self):
        sn = self.controller.get_runtime_snapshot()
        self._set_text(self.session, "\n".join([
            f"Active: {sn.get('active',False)}", f"Running: {sn.get('running',False)}", f"Session ID: {sn.get('session_id','')}", f"Goal: {sn.get('goal','')}", f"Status: {sn.get('status','')}", f"Active Model: {sn.get('active_model','')}", f"Planner Model: {sn.get('planner_model','')}", f"Executor Model: {sn.get('executor_model','')}", f"Pending Tasks: {sn.get('pending_task_count',0)}", f"Completed Tasks: {sn.get('completed_task_count',0)}", f"Failed Tasks: {sn.get('failed_task_count',0)}", "", "Last Action:", sn.get('last_action','') or '(none)'
        ]))
        for i in self.queue.get_children(): self.queue.delete(i)
        for t in sn.get("pending_tasks", []): self.queue.insert("", "end", values=(t.get("kind",""), t.get("priority",""), t.get("status",""), t.get("title","")))
        self._set_text(self.notes, "\n".join(sn.get("notes", [])[-20:]) or "No notes yet.")

    def _schedule_refresh(self):
        if self._refresh_job: self.after_cancel(self._refresh_job)
        self._refresh_job = self.after(self.controller.get_settings().get("GUI_REFRESH_MS",1500), self._auto_refresh)

    def _auto_refresh(self):
        self._refresh_job = None; self.refresh_all(); self._schedule_refresh()

    def run_goal(self):
        goal = self.goal.get("1.0","end").strip()
        if not goal: return messagebox.showinfo("Goal Required", "Enter a goal before starting the runtime.")
        if self._runner and self._runner.is_alive(): return messagebox.showinfo("Already Running", "The runtime is already executing a goal.")
        self.controller.set_goal(goal); self.summary.set(f"Running goal: {goal[:120]}")
        self._runner = threading.Thread(target=self._run_worker, args=(goal,), daemon=True); self._runner.start()

    def _run_worker(self, goal):
        try: snap = self.controller.run_goal(goal)
        except Exception as e: self.after(0, lambda: self._run_error(str(e))); return
        self.after(0, lambda: self._run_done(snap))

    def _run_error(self, msg): self.summary.set(f"Run failed: {msg}"); messagebox.showerror("Run Error", msg); self.refresh_all()
    def _run_done(self, snap): self.summary.set(f"Run finished with status: {snap.get('status','unknown')}"); self.refresh_all()
    def stop_goal(self): self.controller.stop_runtime(); self.summary.set("Stop requested."); self.refresh_all()

    def warmup(self):
        def work(): self.after(0, lambda: self.summary.set("Warming up current model...")); res = self.controller.warmup_current_model(); self.after(0, lambda: self._warmup_done(res))
        threading.Thread(target=work, daemon=True).start()

    def _warmup_done(self, res): self.summary.set(f"Warmup {'ok' if res['warmup_ok'] else 'incomplete'} for {res['model_name']}" if res["backend_reachable"] else "Warmup failed because backend is offline."); self.refresh_all()

    def _schedule_save(self, key, cb):
        if key in self._jobs: self.after_cancel(self._jobs[key])
        self._jobs[key] = self.after(180, cb)

    def _schedule_num(self, key, var, cast):
        if self._suspend: return
        raw = str(var.get()).strip()
        if raw in {"", "-", ".", "-."}: return
        try: cast(raw)
        except Exception: return self.settings_status.set(f"Waiting for a valid numeric value for {key}.")
        self._schedule_save(key, lambda: self._save_num(key, raw, cast))

    def _schedule_region(self, field, var):
        if self._suspend: return
        raw = str(var.get()).strip()
        if raw in {"", "-"}: return
        try: int(raw)
        except Exception: return self.settings_status.set(f"Waiting for a valid screen region value for {field}.")
        self._schedule_save(f"SCREEN_REGION.{field}", lambda: self._save_region(field, raw))

    def _save_num(self, key, raw, cast):
        self._jobs.pop(key, None)
        try:
            val = cast(raw); self.controller.update_setting(key, val); self.settings_status.set(f"Saved and applied {key} = {val}")
            if key == "GUI_REFRESH_MS": self._schedule_refresh()
            self.refresh_all()
        except Exception as e: self.settings_status.set(f"Could not save {key}: {e}")

    def _save_region(self, field, raw):
        self._jobs.pop(f"SCREEN_REGION.{field}", None)
        try: val = int(raw); self.controller.update_screen_region_value(field, val); self.settings_status.set(f"Saved and applied SCREEN_REGION.{field} = {val}"); self.refresh_all()
        except Exception as e: self.settings_status.set(f"Could not save screen region {field}: {e}")

    def _save_toggle(self, key, val):
        if self._suspend: return
        try:
            self.controller.update_setting(key, val); self.settings_status.set(f"Saved and applied {key} = {val}")
            self.monitor_state.set(f"Monitor: {'running' if self.controller.is_monitoring() else 'stopped'}")
            self.refresh_all()
        except Exception as e: self.settings_status.set(f"Could not save {key}: {e}")

    def _save_text(self, key, val):
        if self._suspend: return
        val = val.strip()
        if not val: return self.settings_status.set(f"{key} cannot be empty.")
        try: self.controller.update_setting(key, val); self.settings_status.set(f"Saved and applied {key} = {val}"); self.refresh_all()
        except Exception as e: self.settings_status.set(f"Could not save {key}: {e}")

    def _on_close(self):
        try:
            self.controller.stop_runtime()
            if not self.controller.get_settings().get("START_MONITOR_ON_GUI", True): self.controller.stop_monitoring()
        finally:
            if self._refresh_job: self.after_cancel(self._refresh_job)
            self.destroy()

def main() -> None:
    AgentDesktopGUI().mainloop()

if __name__ == "__main__":
    main()
