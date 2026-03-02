# config.py
# Role: Global constants. Imported by nearly everything.
# Exports: MODEL_NAME, OLLAMA_URL, SCREEN_REGION, LOOP_DELAY, MAX_RETRIES, DEBUG, BLOCK_CPU_COMPUTE, OLLAMA_NUM_GPU

# Model configuration
MODEL_NAME: str = "qwen2.5-coder:7b"
OLLAMA_URL: str = "http://localhost:11434"

# GPU and memory configuration
BLOCK_CPU_COMPUTE: bool = True   # Block CPU from doing ANY GPU calculations
OLLAMA_NUM_GPU: int = 999        # Force ALL layers to GPU (999 = unlimited, offload to RAM if VRAM full)

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
