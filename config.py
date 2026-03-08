from __future__ import annotations

import json, os, sys
from copy import deepcopy
from pathlib import Path

SETTINGS_FILE = Path("agent_settings.json")
DEFAULT_SETTINGS = {
    "MODEL_NAME": "qwen2.5-coder:7b",
    "OLLAMA_URL": "http://localhost:11434",
    "BLOCK_CPU_COMPUTE": True,
    "OLLAMA_NUM_GPU": 999,
    "SCREEN_REGION": {"top": 0, "left": 0, "width": 1920, "height": 1080},
    "LOOP_DELAY": 2.0,
    "MAX_RETRIES": 3,
    "DEBUG": False,
    "GUI_REFRESH_MS": 1500,
    "START_MONITOR_ON_GUI": True,
}

def _norm_region(v: dict | None) -> dict:
    r = deepcopy(DEFAULT_SETTINGS["SCREEN_REGION"])
    if isinstance(v, dict):
        for k in r:
            try: r[k] = int(v.get(k, r[k]))
            except Exception: pass
    r["width"] = max(1, int(r["width"]))
    r["height"] = max(1, int(r["height"]))
    return r

def _norm(raw: dict | None) -> dict:
    d = deepcopy(DEFAULT_SETTINGS)
    if isinstance(raw, dict):
        for k, v in raw.items():
            if k == "SCREEN_REGION": d[k] = _norm_region(v)
            elif k in d: d[k] = v
    d["MODEL_NAME"] = str(d["MODEL_NAME"] or DEFAULT_SETTINGS["MODEL_NAME"]).strip() or DEFAULT_SETTINGS["MODEL_NAME"]
    d["OLLAMA_URL"] = str(d["OLLAMA_URL"] or DEFAULT_SETTINGS["OLLAMA_URL"]).strip() or DEFAULT_SETTINGS["OLLAMA_URL"]
    d["BLOCK_CPU_COMPUTE"] = bool(d["BLOCK_CPU_COMPUTE"])
    d["OLLAMA_NUM_GPU"] = max(0, int(d["OLLAMA_NUM_GPU"]))
    d["SCREEN_REGION"] = _norm_region(d.get("SCREEN_REGION"))
    d["LOOP_DELAY"] = max(0.1, float(d["LOOP_DELAY"]))
    d["MAX_RETRIES"] = max(1, int(d["MAX_RETRIES"]))
    d["DEBUG"] = bool(d["DEBUG"])
    d["GUI_REFRESH_MS"] = max(500, int(d["GUI_REFRESH_MS"]))
    d["START_MONITOR_ON_GUI"] = bool(d["START_MONITOR_ON_GUI"])
    return d

def _read() -> dict:
    if not SETTINGS_FILE.exists(): return {}
    try: return json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except Exception: return {}

def load_runtime_settings() -> dict:
    return _norm(_read())

def save_runtime_settings(settings: dict) -> dict:
    data = _norm(settings)
    SETTINGS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return data

def _set_env() -> None:
    if BLOCK_CPU_COMPUTE:
        os.environ["CUDA_LAUNCH_BLOCKING"] = "1"
        os.environ["CUDA_DEVICE_ORDER"] = "PCI_BUS_ID"
        os.environ["CUDA_VISIBLE_DEVICES"] = "0"
        os.environ["OMP_NUM_THREADS"] = "1"
        os.environ["MKL_NUM_THREADS"] = "1"
    else:
        for k in ["CUDA_LAUNCH_BLOCKING", "CUDA_DEVICE_ORDER", "CUDA_VISIBLE_DEVICES", "OMP_NUM_THREADS", "MKL_NUM_THREADS"]:
            os.environ.pop(k, None)

def _set_globals(s: dict) -> None:
    global MODEL_NAME, OLLAMA_URL, BLOCK_CPU_COMPUTE, OLLAMA_NUM_GPU, SCREEN_REGION, LOOP_DELAY, MAX_RETRIES, DEBUG, GUI_REFRESH_MS, START_MONITOR_ON_GUI
    MODEL_NAME = s["MODEL_NAME"]
    OLLAMA_URL = s["OLLAMA_URL"]
    BLOCK_CPU_COMPUTE = s["BLOCK_CPU_COMPUTE"]
    OLLAMA_NUM_GPU = s["OLLAMA_NUM_GPU"]
    SCREEN_REGION = deepcopy(s["SCREEN_REGION"])
    LOOP_DELAY = s["LOOP_DELAY"]
    MAX_RETRIES = s["MAX_RETRIES"]
    DEBUG = s["DEBUG"]
    GUI_REFRESH_MS = s["GUI_REFRESH_MS"]
    START_MONITOR_ON_GUI = s["START_MONITOR_ON_GUI"]

def _sync() -> None:
    mods = sys.modules
    if "ollama_client" in mods:
        m = mods["ollama_client"]; m.MODEL_NAME = MODEL_NAME; m.OLLAMA_URL = OLLAMA_URL; m.MAX_RETRIES = MAX_RETRIES; m.DEBUG = DEBUG
    if "model_adapter" in mods:
        mods["model_adapter"].MODEL_NAME = MODEL_NAME
    if "monitor" in mods:
        m = mods["monitor"]; m.MODEL_NAME = MODEL_NAME; m.OLLAMA_URL = OLLAMA_URL; m.DEBUG = DEBUG
    if "agent_loop" in mods:
        m = mods["agent_loop"]
        m.MODEL_NAME = MODEL_NAME; m.OLLAMA_URL = OLLAMA_URL; m.LOOP_DELAY = LOOP_DELAY; m.DEBUG = DEBUG; m.BLOCK_CPU_COMPUTE = BLOCK_CPU_COMPUTE; m.OLLAMA_NUM_GPU = OLLAMA_NUM_GPU
        if hasattr(m, "interpreter"):
            try:
                m.interpreter.llm.model = f"ollama/{MODEL_NAME}"
                m.interpreter.llm.api_base = OLLAMA_URL
                m.interpreter.llm.num_gpu = OLLAMA_NUM_GPU
                m.interpreter.verbose = DEBUG
            except Exception:
                pass
        if hasattr(m, "_model_adapter") and "model_adapter" in mods:
            try: m._model_adapter = mods["model_adapter"].build_default_adapter()
            except Exception: pass
        sess = getattr(m, "_active_session", None)
        if sess is not None:
            sess.active_model = MODEL_NAME; sess.planner_model = MODEL_NAME; sess.executor_model = MODEL_NAME

def get_runtime_settings() -> dict:
    return {
        "MODEL_NAME": MODEL_NAME,
        "OLLAMA_URL": OLLAMA_URL,
        "BLOCK_CPU_COMPUTE": BLOCK_CPU_COMPUTE,
        "OLLAMA_NUM_GPU": OLLAMA_NUM_GPU,
        "SCREEN_REGION": deepcopy(SCREEN_REGION),
        "LOOP_DELAY": LOOP_DELAY,
        "MAX_RETRIES": MAX_RETRIES,
        "DEBUG": DEBUG,
        "GUI_REFRESH_MS": GUI_REFRESH_MS,
        "START_MONITOR_ON_GUI": START_MONITOR_ON_GUI,
    }

def apply_runtime_settings(settings: dict | None = None) -> dict:
    s = _norm(settings if settings is not None else load_runtime_settings())
    _set_globals(s); _set_env(); _sync(); return get_runtime_settings()

def update_setting(key: str, value) -> dict:
    s = get_runtime_settings()
    if key == "SCREEN_REGION": raise ValueError("Use update_screen_region_value().")
    if key not in s: raise KeyError(f"Unknown setting: {key}")
    s[key] = value
    return apply_runtime_settings(save_runtime_settings(s))

def update_screen_region_value(field: str, value: int) -> dict:
    if field not in DEFAULT_SETTINGS["SCREEN_REGION"]: raise KeyError(f"Unknown screen region field: {field}")
    s = get_runtime_settings(); r = deepcopy(s["SCREEN_REGION"]); r[field] = int(value); s["SCREEN_REGION"] = r
    return apply_runtime_settings(save_runtime_settings(s))

_initial = load_runtime_settings(); _set_globals(_initial); _set_env()
