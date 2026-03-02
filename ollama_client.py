# ollama_client.py
# Role: Interface to local Ollama model via HTTP API.
# Imports from: config.py, requests
# Contract: check_ollama_running() -> bool
#           load_model(model_name: str) -> bool
#           query_model(prompt: str, system: str | None = None) -> str

import requests

from config import MODEL_NAME, OLLAMA_URL, MAX_RETRIES, DEBUG


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


def query_model(prompt: str, system: str | None = None) -> str:
    """
    Sends a prompt to the Ollama model via /api/chat.
    Returns the model's response as a plain string.
    Raises ConnectionError if Ollama is not running or all retries fail.
    """
    if not check_ollama_running():
        raise ConnectionError(f"Ollama is not reachable at {OLLAMA_URL}")

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    payload = {
        "model": MODEL_NAME,
        "messages": messages,
        "stream": False,
    }

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            if DEBUG:
                print(f"[ollama_client] Query attempt {attempt}/{MAX_RETRIES}")
            response = requests.post(
                f"{OLLAMA_URL}/api/chat",
                json=payload,
                timeout=60,
            )
            if response.status_code == 200:
                data = response.json()
                return data["message"]["content"]
            else:
                if DEBUG:
                    print(f"[ollama_client] HTTP {response.status_code}: {response.text}")
        except Exception as e:
            if DEBUG:
                print(f"[ollama_client] Exception on attempt {attempt}: {e}")

    raise ConnectionError(
        f"Failed to query model after {MAX_RETRIES} attempts. Check Ollama."
    )
