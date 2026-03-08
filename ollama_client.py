# ollama_client.py
# Role: Interface to local Ollama model via HTTP API.
# Imports from: config.py, requests, runtime_models.py
# Contract: check_ollama_running() -> bool
#           load_model(model_name: str) -> bool
#           query_model(prompt: str, system: str | None = None) -> str
#           query_model_reply(prompt: str, system: str | None = None,
#                            model_name: str | None = None,
#                            timeout: int = 60) -> ModelReply

from __future__ import annotations

from typing import Any

import requests

from config import MODEL_NAME, OLLAMA_URL, MAX_RETRIES, DEBUG
from runtime_models import ModelReply


def check_ollama_running() -> bool:
    """
    Checks if Ollama is reachable at OLLAMA_URL.
    Returns True if HTTP 200, False on any exception.
    """
    try:
        response = requests.get(OLLAMA_URL, timeout=3)
        return response.status_code == 200
    except Exception:
        return False


def load_model(model_name: str) -> bool:
    """
    Warms up / preloads a model in Ollama.
    Sends an empty prompt with keep_alive to load weights into VRAM.
    Returns True if successful, False on failure.
    """
    try:
        payload = {
            "model": model_name,
            "prompt": "",
            "keep_alive": "5m",
        }
        response = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json=payload,
            timeout=30,
        )
        success = response.status_code == 200
        if DEBUG:
            if success:
                print(f"[ollama_client] Model '{model_name}' loaded successfully.")
            else:
                print(f"[ollama_client] Model load failed: HTTP {response.status_code}")
        return success
    except Exception as e:
        if DEBUG:
            print(f"[ollama_client] Model load exception: {e}")
        return False


def _build_messages(prompt: str, system: str | None = None) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    return messages


def _parse_chat_response(data: dict[str, Any], requested_model: str) -> ModelReply:
    message = data.get("message", {}) or {}
    content = str(message.get("content", ""))
    model_name = str(data.get("model", requested_model or MODEL_NAME))
    stop_reason = str(data.get("done_reason", ""))

    usage = {
        "prompt_eval_count": data.get("prompt_eval_count"),
        "eval_count": data.get("eval_count"),
        "prompt_eval_duration": data.get("prompt_eval_duration"),
        "eval_duration": data.get("eval_duration"),
        "total_duration": data.get("total_duration"),
        "load_duration": data.get("load_duration"),
    }
    usage = {k: v for k, v in usage.items() if v is not None}

    metadata = {
        "done": data.get("done"),
        "created_at": data.get("created_at"),
        "backend": "ollama",
        "message": message,
    }

    return ModelReply(
        content=content,
        model_name=model_name,
        raw=data,
        stop_reason=stop_reason,
        usage=usage,
        metadata=metadata,
    )


def query_model_reply(
    prompt: str,
    system: str | None = None,
    model_name: str | None = None,
    timeout: int = 60,
) -> ModelReply:
    """
    Sends a prompt to the Ollama model via /api/chat.
    Returns a typed ModelReply for the queue-based runtime migration.
    Raises ConnectionError if Ollama is not running or all retries fail.
    """
    if not check_ollama_running():
        raise ConnectionError(f"Ollama is not reachable at {OLLAMA_URL}")

    requested_model = model_name or MODEL_NAME
    payload = {
        "model": requested_model,
        "messages": _build_messages(prompt, system),
        "stream": False,
    }

    last_error = ""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            if DEBUG:
                print(
                    f"[ollama_client] Query attempt {attempt}/{MAX_RETRIES} "
                    f"for model '{requested_model}'"
                )
            response = requests.post(
                f"{OLLAMA_URL}/api/chat",
                json=payload,
                timeout=timeout,
            )
            if response.status_code == 200:
                return _parse_chat_response(response.json(), requested_model)

            last_error = f"HTTP {response.status_code}: {response.text}"
            if DEBUG:
                print(f"[ollama_client] {last_error}")
        except Exception as e:
            last_error = str(e)
            if DEBUG:
                print(f"[ollama_client] Exception on attempt {attempt}: {e}")

    raise ConnectionError(
        f"Failed to query model after {MAX_RETRIES} attempts. Last error: {last_error}"
    )


def query_model(prompt: str, system: str | None = None) -> str:
    """
    Sends a prompt to the Ollama model via /api/chat.
    Returns the model's response as a plain string.
    Raises ConnectionError if Ollama is not running or all retries fail.
    """
    reply = query_model_reply(prompt=prompt, system=system, model_name=MODEL_NAME, timeout=60)
    return reply.content
