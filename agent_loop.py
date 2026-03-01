# agent_loop.py
# Role: Core autonomous goal loop. Orchestrates all components.
# Imports from: config.py, vision.py, ollama_client.py, screen_capture.py, open-interpreter
# Contract: run(goal: str) -> None
#           step(goal: str, screen_state: dict) -> str
#           stop() -> None
# NOTE: This is the ONLY file that calls vision.py and ollama_client.py directly.
# NOTE: interpreter object is instantiated ONCE here and reused for the session.

import time

from interpreter import interpreter

from config import (
    MODEL_NAME,
    OLLAMA_URL,
    LOOP_DELAY,
    DEBUG,
)
from vision import get_screen_state
from ollama_client import check_ollama_running, query_model

# =============================================================================
# Open Interpreter — configured once at module load
# =============================================================================
interpreter.llm.model = f"ollama/{MODEL_NAME}"
interpreter.llm.api_base = OLLAMA_URL
interpreter.auto_run = True          # execute code blocks without asking
interpreter.verbose = DEBUG          # mirror DEBUG flag for OI internal logging
interpreter.offline = True           # never phone home — local only

# Internal state
_running = False

# =============================================================================
# System prompt injected into every OI session
# =============================================================================
_SYSTEM_PROMPT = """
You are an autonomous desktop agent running on a Windows 10 machine.
You observe the current screen state and take actions to accomplish the user's goal.
You have access to Python and shell execution via Open Interpreter.
Always reason step by step. After each action, wait for screen feedback before proceeding.
When the goal is fully accomplished, respond with exactly: GOAL_COMPLETE
""".strip()


def step(goal: str, screen_state: dict) -> str:
    """
    Runs a single agent tick.
    Builds a prompt from the current goal + screen state,
    queries the model via Open Interpreter, and returns the response string.
    """
    description = screen_state.get("description", "No screen data available.")
    visible_text = screen_state.get("text", "")

    prompt = (
        f"GOAL: {goal}\n\n"
        f"CURRENT SCREEN: {description}\n"
    )
    if visible_text:
        prompt += f"VISIBLE TEXT: {visible_text[:500]}\n"

    if DEBUG:
        print(f"[agent_loop] step() prompt:\n{prompt}")

    # Route through Open Interpreter — returns list of message dicts
    response_messages = interpreter.chat(prompt, display=DEBUG, stream=False)

    # Extract the last assistant message content as the action string
    action = ""
    for msg in reversed(response_messages):
        if msg.get("role") == "assistant" and msg.get("content"):
            action = msg["content"].strip()
            break

    if DEBUG:
        print(f"[agent_loop] step() action: {action}")

    return action


def run(goal: str) -> None:
    """
    Main entry point for the agent loop.
    Accepts a plain-English goal string.
    Runs continuously until GOAL_COMPLETE is returned or user interrupts (Ctrl+C).
    """
    global _running

    if not check_ollama_running():
        raise ConnectionError(
            f"Ollama is not reachable. Start Ollama before calling agent_loop.run()."
        )

    # Reset interpreter conversation for a fresh session
    interpreter.messages = []
    interpreter.system_message = _SYSTEM_PROMPT

    _running = True
    tick = 0

    print(f"[agent_loop] Starting. Goal: {goal}")

    try:
        while _running:
            tick += 1
            if DEBUG:
                print(f"[agent_loop] Tick {tick}")

            # Capture and analyze current screen state
            screen_state = get_screen_state()

            # Run one agent step
            action = step(goal, screen_state)

            # Check for completion signal
            if "GOAL_COMPLETE" in action:
                print(f"[agent_loop] Goal complete after {tick} tick(s).")
                break

            # Pace the loop
            time.sleep(LOOP_DELAY)

    except KeyboardInterrupt:
        print("[agent_loop] Interrupted by user.")
    finally:
        _running = False
        if DEBUG:
            print(f"[agent_loop] Loop exited after {tick} tick(s).")


def stop() -> None:
    """
    Gracefully stops the agent loop and cleans up the interpreter session.
    Sets _running to False so the run() while loop exits on next iteration.
    Resets interpreter message history to free memory.
    """
    global _running
    _running = False
    interpreter.messages = []
    if DEBUG:
        print("[agent_loop] stop() called. Interpreter session cleared.")
