# main.py
# Role: Entry point. Wires config + agent loop together. Minimal logic.
# Imports from: config.py, agent_loop.py
# Contract: main() -> None
# NOTE: Does NOT import vision.py or ollama_client.py directly.
# NOTE: Does NOT configure the interpreter — that is agent_loop.py's responsibility.

import sys

from config import DEBUG, MODEL_NAME, OLLAMA_URL
import agent_loop

# ollama_client is imported only to run the startup check cleanly before
# handing control to agent_loop. It is NOT called again from main.py.
from ollama_client import check_ollama_running, load_model


def main() -> None:
    """
    Entry point for the desktop agent.
    1. Prints startup info.
    2. Confirms Ollama is reachable.
    3. Warms up the model.
    4. Prompts the user for a goal.
    5. Hands off to agent_loop.run(goal).
    """
    print("=" * 60)
    print(" AgentDesktopTest")
    print(f" Model : {MODEL_NAME}")
    print(f" Ollama: {OLLAMA_URL}")
    print(f" Debug : {DEBUG}")
    print("=" * 60)

    # --- Step 1: Confirm Ollama is live ---
    print("[main] Checking Ollama...")
    if not check_ollama_running():
        print(
            f"[main] ERROR: Ollama is not running at {OLLAMA_URL}.\n"
            f"       Start it with: ollama serve"
        )
        sys.exit(1)
    print("[main] Ollama is live.")

    # --- Step 2: Warm up the model ---
    print(f"[main] Loading model '{MODEL_NAME}'...")
    if not load_model(MODEL_NAME):
        print(
            f"[main] WARNING: Model warm-up failed. "
            f"Proceeding anyway — first query may be slow."
        )
    else:
        print(f"[main] Model ready.")

    # --- Step 3: Get goal from user ---
    print()
    try:
        goal = input("Enter goal for the agent: ").strip()
    except (KeyboardInterrupt, EOFError):
        print("\n[main] Cancelled.")
        sys.exit(0)

    if not goal:
        print("[main] No goal entered. Exiting.")
        sys.exit(0)

    # --- Step 4: Hand off to agent loop ---
    print(f"[main] Starting agent loop with goal: {goal!r}")
    print("       Press Ctrl+C at any time to stop.\n")

    try:
        agent_loop.run(goal)
    except ConnectionError as e:
        print(f"[main] Connection error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"[main] Unexpected error: {e}")
        if DEBUG:
            raise
        sys.exit(1)

    print("[main] Agent loop finished. Goodbye.")


if __name__ == "__main__":
    main()
