# ollama_client.py
# Role: Interface to local Ollama model via HTTP API.
# Imports from: config.py, requests
# Contract: query_model(), load_model(), check_ollama_running()

import requests
from config import MODEL_NAME, OLLAMA_URL, MAX_RETRIES, DEBUG


def check_ollama_running() -> bool:
    """
    Pings OLLAMA_URL to confirm the Ollama service is live.
    Returns True if reachable, False otherwise.
    """
    try:
        resp = requests.get(OLLAMA_URL, timeout=3)
        return resp.status_code == 200
    except requests.exceptions.RequestException:
        return False


def load_model(model_name: str) -> bool:
    """
    Warms up / preloads a model in Ollama by sending a keep-alive generate request.
    Returns True if successful, False if failed.
    """
    url = f"{OLLAMA_URL}/api/generate"
    payload = {
        "model": model_name,
        "prompt": "",
        "keep_alive": "5m",
    }
    try:
        resp = requests.post(url, json=payload, timeout=30)
        success = resp.status_code == 200
        if DEBUG:
            print(f"[ollama_client] load_model({model_name!r}) -> {success}")
        return success
    except requests.exceptions.RequestException as e:
        if DEBUG:
            print(f"[ollama_client] load_model failed: {e}")
        return False


def query_model(prompt: str, system: str | None = None) -> str:
    """
    Sends a prompt to the Ollama model and returns the response as a string.
    Uses MODEL_NAME and OLLAMA_URL from config.py.
    Retries up to MAX_RETRIES times on transient failures.
    Raises ConnectionError if Ollama is not running or all retries fail.
    """
    if not check_ollama_running():
        raise ConnectionError(
            f"Ollama is not reachable at {OLLAMA_URL}. "
            "Ensure the Ollama service is running before calling query_model()."
        )

    url = f"{OLLAMA_URL}/api/chat"
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    payload = {
        "model": MODEL_NAME,
        "messages": messages,
        "stream": False,
    }

    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.post(url, json=payload, timeout=60)
            resp.raise_for_status()
            data = resp.json()
            result = data["message"]["content"]
            if DEBUG:
                print(f"[ollama_client] query_model attempt {attempt} succeeded.")
            return result
        except (requests.exceptions.RequestException, KeyError) as e:
            last_error = e
            if DEBUG:
                print(f"[ollama_client] query_model attempt {attempt}/{MAX_RETRIES} failed: {e}")

    raise ConnectionError(
        f"query_model failed after {MAX_RETRIES} attempts. Last error: {last_error}"
    )
