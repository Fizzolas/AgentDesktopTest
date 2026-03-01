# vision.py
# Role: Analyzes screen frames. Returns structured description for the agent.
# Imports from: screen_capture.py, cv2, easyocr, numpy
# Contract: analyze_frame(img: np.ndarray) -> dict
#           get_screen_state(region: dict | None = None) -> dict
# Return format: {"description": str, "elements": list, "text": str}

import numpy as np
import cv2
import easyocr

from screen_capture import capture_screen

# EasyOCR reader is initialized once at module load to avoid repeated GPU overhead.
# gpu=True leverages the RTX 4070 for OCR inference.
_reader = easyocr.Reader(["en"], gpu=True, verbose=False)


def analyze_frame(img: np.ndarray) -> dict:
    """
    Analyzes a BGR screen frame.
    Returns a structured dict:
      {
        "description": str,   # plain-English summary of screen content
        "elements":    list,  # list of dicts describing detected UI regions
        "text":        str,   # all OCR-extracted text joined as a single string
      }

    Each element in "elements" has the shape:
      {
        "type":   str,   # e.g. "text_block", "button_candidate", "image_region"
        "bbox":   list,  # [x, y, w, h] in pixels
        "text":   str,   # OCR text for this element (empty string if none)
        "confidence": float  # OCR confidence 0.0-1.0 (0.0 if no text detected)
      }
    """
    elements = []
    all_text_parts = []

    # --- OCR pass: extract text and bounding boxes ---
    ocr_results = _reader.readtext(img)
    # ocr_results format: [ ([[x1,y1],[x2,y1],[x2,y2],[x1,y2]], text, confidence), ... ]

    for (bbox_points, text, confidence) in ocr_results:
        if not text.strip():
            continue
        xs = [pt[0] for pt in bbox_points]
        ys = [pt[1] for pt in bbox_points]
        x = int(min(xs))
        y = int(min(ys))
        w = int(max(xs) - x)
        h = int(max(ys) - y)
        all_text_parts.append(text)
        elements.append({
            "type": "text_block",
            "bbox": [x, y, w, h],
            "text": text,
            "confidence": round(float(confidence), 3),
        })

    # --- Contour pass: find large non-text rectangular regions (button/panel candidates) ---
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blurred, threshold1=50, threshold2=150)
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    img_area = img.shape[0] * img.shape[1]
    for cnt in contours:
        x, y, w, h = cv2.boundingRect(cnt)
        area = w * h
        # Skip tiny noise and screen-filling contours
        if area < 800 or area > img_area * 0.6:
            continue
        aspect = w / h if h > 0 else 0
        # Button-like: reasonably wide, not too tall
        if 1.5 <= aspect <= 10 and 10 <= h <= 80:
            elements.append({
                "type": "button_candidate",
                "bbox": [x, y, w, h],
                "text": "",
                "confidence": 0.0,
            })

    # --- Build description ---
    text_joined = " ".join(all_text_parts).strip()
    n_text = sum(1 for e in elements if e["type"] == "text_block")
    n_btn = sum(1 for e in elements if e["type"] == "button_candidate")

    if text_joined:
        description = (
            f"Screen contains {n_text} text block(s) and {n_btn} button candidate(s). "
            f"Visible text (partial): {text_joined[:300]}"
        )
    else:
        description = (
            f"Screen contains no readable text. "
            f"Detected {n_btn} button candidate(s) via contour analysis."
        )

    return {
        "description": description,
        "elements": elements,
        "text": text_joined,
    }


def get_screen_state(region: dict | None = None) -> dict:
    """
    Convenience wrapper: captures screen then analyzes it in one call.
    Calls capture_screen(region) -> analyze_frame(img).
    Returns same format as analyze_frame():
      {"description": str, "elements": list, "text": str}
    """
    img = capture_screen(region)
    return analyze_frame(img)
