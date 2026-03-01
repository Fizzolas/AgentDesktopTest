# config.py
# Global settings and configuration
# Imported by: main.py, agent_loop.py, ollama_client.py
# Exports: MODEL_NAME, OLLAMA_URL, SCREEN_REGION, LOOP_DELAY, MAX_RETRIES, DEBUG

# --- Model ---
MODEL_NAME: str = "qwen2.5-coder:7b"

# --- Ollama endpoint ---
OLLAMA_URL: str = "http://localhost:11434"

# --- Screen capture region (full primary monitor) ---
SCREEN_REGION: dict = {"top": 0, "left": 0, "width": 1920, "height": 1080}

# --- Agent loop timing ---
LOOP_DELAY: float = 2.0  # seconds between agent loop ticks

# --- Reliability ---
MAX_RETRIES: int = 3  # max retries on model query failure

# --- Logging ---
DEBUG: bool = False  # set True for verbose output
