# config.py
# Role: Global constants. Imported by nearly everything.
# Exports: MODEL_NAME, OLLAMA_URL, SCREEN_REGION, LOOP_DELAY, MAX_RETRIES, DEBUG, FORCE_CPU_ONLY, OLLAMA_NUM_GPU, OLLAMA_NUM_THREAD

# Model configuration
MODEL_NAME: str = "qwen2.5-coder:7b"
OLLAMA_URL: str = "http://localhost:11434"

# GPU and memory configuration
FORCE_CPU_ONLY: bool = True  # Block GPU usage entirely - forces CPU-only inference
OLLAMA_NUM_GPU: int = 0      # Number of GPU layers to offload (0 = all in RAM)
OLLAMA_NUM_THREAD: int = 10  # CPU threads for inference (adjust based on CPU cores)

# Screen capture region (full primary monitor by default)
SCREEN_REGION: dict = {
    "top": 0,
    "left": 0,
    "width": 1920,
    "height": 1080,
}

# Agent loop timing
LOOP_DELAY: float = 2.0  # seconds between agent ticks

# Retry behavior
MAX_RETRIES: int = 3  # max retries on model query failure

# Debug mode
DEBUG: bool = False  # set to True for verbose logging
