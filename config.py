from __future__ import annotations

import json
import os
import sys
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


def _normalize_screen_region(value: dict | None) -> dict:
    region = deepcopy(DEFAULT_SETTINGS["SCREEN_REGION"])
    if isinstance(value, dict):
        for key in region:
            try:
                region[key] = int(value.get(key, region[key]))
            except Exception:
                pass
    region["width"] = max(1, int(region["width"]))
    region["height"] = max(1, int(region["height"]))
    return region



def _normalize_settings(raw: dict | None) -> dict:
    data = deepcopy(DEFAULT_SETTINGS)
    if isinstance(raw, dict):
        for key, value in raw.items():
            if key == "SCREEN_REGION":
                data[key] = _normalize_screen_region(value)
            elif key in data:
                data[key] = value

    data["MODEL_NAME"] = str(data["MODEL_NAME"] or DEFAULT_SETTINGS["MODEL_NAME"]).strip() or DEFAULT_SETTINGS["MODEL_NAME"]
    data["OLLAMA_URL"] = str(data["OLLAMA_URL"] or DEFAULT_SETTINGS["OLLAMA_URL"]).strip() or DEFAULT_SETTINGS["OLLAMA_URL"]
    data["BLOCK_CPU_COMPUTE"] = bool(data["BLOCK_CPU_COMPUTE"])
    data["OLLAMA_NUM_GPU"] = max(0, int(data["OLLAMA_NUM_GPU"]))
    data["SCREEN_REGION"] = _normalize_screen_region(data.get("SCREEN_REGION"))
    data["LOOP_DELAY"] = max(0.1, float(data["LOOP_DELAY"]))
    data["MAX_RETRIES"] = max(1, int(data["MAX_RETRIES"]))
    data["DEBUG"] = bool(data["DEBUG"])
    data["GUI_REFRESH_MS"] = max(500, int(data["GUI_REFRESH_MS"]))
    data["START_MONITOR_ON_GUI"] = bool(data["START_MONITOR_ON_GUI"])
    return data



def _read_settings_file() -> dict:
    if not SETTINGS_FILE.exists():
        return {}
    try:
        return json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}



def load_runtime_settings() -> dict:
    return _normalize_settings(_read_settings_file())



def save_runtime_settings(settings: dict) -> dict:
    normalized = _normalize_settings(settings)
    SETTINGS_FILE.write_text(json.dumps(normalized, indent=2), encoding="utf-8")
    return normalized



def _apply_environment_flags() -> None:
    if BLOCK_CPU_COMPUTE:
        os.environ["CUDA_LAUNCH_BLOCKING"] = "1"
        os.environ["CUDA_DEVICE_ORDER"] = "PCI_BUS_ID"
        os.environ["CUDA_VISIBLE_DEVICES"] = "0"
        os.environ["OMP_NUM_THREADS"] = "1"
        os.environ["MKL_NUM_THREADS"] = "1"
    else:
        for key in [
            "CUDA_LAUNCH_BLOCKING",
            "CUDA_DEVICE_ORDER",
            "CUDA_VISIBLE_DEVICES",
            "OMP_NUM_THREADS",
            "MKL_NUM_THREADS",
        ]:
            os.environ.pop(key, None)



def _set_module_globals(settings: dict) -> None:
    global MODEL_NAME, OLLAMA_URL, BLOCK_CPU_COMPUTE, OLLAMA_NUM_GPU
    global SCREEN_REGION, LOOP_DELAY, MAX_RETRIES, DEBUG, GUI_REFRESH_MS, START_MONITOR_ON_GUI

    MODEL_NAME = settings["MODEL_NAME"]
    OLLAMA_URL = settings["OLLAMA_URL"]
    BLOCK_CPU_COMPUTE = settings["BLOCK_CPU_COMPUTE"]
    OLLAMA_NUM_GPU = settings["OLLAMA_NUM_GPU"]
    SCREEN_REGION = deepcopy(settings["SCREEN_REGION"])
    LOOP_DELAY = settings["LOOP_DELAY"]
    MAX_RETRIES = settings["MAX_RETRIES"]
    DEBUG = settings["DEBUG"]
    GUI_REFRESH_MS = settings["GUI_REFRESH_MS"]
    START_MONITOR_ON_GUI = settings["START_MONITOR_ON_GUI"]



def _sync_loaded_modules() -> None:
    loaded = sys.modules

    if "ollama_client" in loaded:
        module = loaded["ollama_client"]
        module.MODEL_NAME = MODEL_NAME
        module.OLLAMA_URL = OLLAMA_URL
        module.MAX_RETRIES = MAX_RETRIES
        module.DEBUG = DEBUG

    if "model_adapter" in loaded:
        loaded["model_adapter"].MODEL_NAME = MODEL_NAME

    if "monitor" in loaded:
        module = loaded["monitor"]
        module.MODEL_NAME = MODEL_NAME
        module.OLLAMA_URL = OLLAMA_URL
        module.DEBUG = DEBUG

    if "agent_loop" in loaded:
        module = loaded["agent_loop"]
        module.MODEL_NAME = MODEL_NAME
        module.OLLAMA_URL = OLLAMA_URL
        module.LOOP_DELAY = LOOP_DELAY
        module.DEBUG = DEBUG
        module.BLOCK_CPU_COMPUTE = BLOCK_CPU_COMPUTE
        module.OLLAMA_NUM_GPU = OLLAMA_NUM_GPU

        if hasattr(module, "interpreter"):
            try:
                module.interpreter.llm.model = f"ollama/{MODEL_NAME}"
                module.interpreter.llm.api_base = OLLAMA_URL
                module.interpreter.llm.num_gpu = OLLAMA_NUM_GPU
                module.interpreter.verbose = DEBUG
            except Exception:
                pass

        if hasattr(module, "_model_adapter") and "model_adapter" in loaded:
            try:
                module._model_adapter = loaded["model_adapter"].build_default_adapter()
            except Exception:
                pass

        session = getattr(module, "_active_session", None)
        if session is not None:
            session.active_model = MODEL_NAME
            session.planner_model = MODEL_NAME
            session.executor_model = MODEL_NAME



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
    normalized = _normalize_settings(settings if settings is not None else load_runtime_settings())
    _set_module_globals(normalized)
    _apply_environment_flags()
    _sync_loaded_modules()
    return get_runtime_settings()



def update_setting(key: str, value) -> dict:
    settings = get_runtime_settings()
    if key == "SCREEN_REGION":
        raise ValueError("Use update_screen_region_value() for partial region updates.")
    if key not in settings:
        raise KeyError(f"Unknown setting: {key}")
    settings[key] = value
    return apply_runtime_settings(save_runtime_settings(settings))



def update_screen_region_value(field: str, value: int) -> dict:
    if field not in DEFAULT_SETTINGS["SCREEN_REGION"]:
        raise KeyError(f"Unknown screen region field: {field}")
    settings = get_runtime_settings()
    region = deepcopy(settings["SCREEN_REGION"])
    region[field] = int(value)
    settings["SCREEN_REGION"] = region
    return apply_runtime_settings(save_runtime_settings(settings))



def reset_runtime_settings() -> dict:
    return apply_runtime_settings(save_runtime_settings(DEFAULT_SETTINGS))


if not SETTINGS_FILE.exists():
    save_runtime_settings(DEFAULT_SETTINGS)

_INITIAL_SETTINGS = load_runtime_settings()
_set_module_globals(_INITIAL_SETTINGS)
_apply_environment_flags()
