from __future__ import annotations

from bootstrap import ensure_runtime_dependencies



def main() -> None:
    ensure_runtime_dependencies()
    try:
        from gui_app import main as gui_main
    except Exception as e:
        print(f"[main] GUI import failed: {e}")
        from shell_main import main as shell_main
        print("[main] Falling back to shell mode.")
        shell_main()
        return

    try:
        gui_main()
    except Exception as e:
        print(f"[main] GUI launch failed: {e}")
        from shell_main import main as shell_main
        print("[main] Falling back to shell mode.")
        shell_main()


if __name__ == "__main__":
    main()
