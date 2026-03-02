# screen_capture.py
# Role: Raw screen grab utility. Base layer — no project imports.
# Imports from: (none — uses mss, numpy only)
# Contract: capture_screen(region: dict | None = None) -> np.ndarray

import numpy as np
import mss


def capture_screen(region: dict | None = None) -> np.ndarray:
    """
    Captures the screen or a specified region.
    Returns a BGR numpy array (uint8, HxWxC format).

    Args:
        region: Optional dict with keys {"top", "left", "width", "height"}.
                If None, captures the full primary monitor.

    Returns:
        np.ndarray: BGR image as uint8 numpy array.
    """
    with mss.mss() as sct:
        if region is None:
            # Capture full primary monitor (index 1)
            # monitors[0] is the virtual combined monitor — not used
            monitor = sct.monitors[1]
        else:
            monitor = region

        # mss returns BGRA by default
        screenshot = sct.grab(monitor)
        img = np.array(screenshot)

        # Strip alpha channel to produce BGR (required by vision.py and OpenCV)
        # Do NOT remove this [:, :, :3] — it is intentional
        return img[:, :, :3]
