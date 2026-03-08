# vision.py
# Role: Analyzes screen frames. Returns structured description for the agent.
# Imports from: screen_capture.py, runtime_models.py, cv2, easyocr, numpy, hashlib, time
# Contract: analyze_frame(img: np.ndarray) -> dict
#           analyze_frame_typed(img: np.ndarray, region: dict | None = None) -> ScreenState
#           get_screen_state(region: dict | None = None) -> dict
#           get_screen_state_typed(region: dict | None = None) -> ScreenState
# Return format (legacy): {"description": str, "elements": list, "text": str}

from __future__ import annotations

import hashlib
import time

import numpy as np
import cv2
import easyocr

from runtime_models import ScreenElement, ScreenState
from screen_capture import capture_screen

# EasyOCR reader is initialized once at module load to avoid repeated GPU overhead.
# gpu=True leverages the RTX 4070 for OCR inference.
_reader = easyocr.Reader(["en"], gpu=True, verbose=False)


def _bbox_from_points(bbox_points: list[list[float]]) -> list[int]:
    xs = [pt[0] for pt in bbox_points]
    ys = [pt[1] for pt in bbox_points]
    x = int(min(xs))
    y = int(min(ys))
    w = int(max(xs) - x)
    h = int(max(ys) - y)
    return [x, y, w, h]


def _make_element_id(element_type: str, bbox: list[int], text: str = "") -> str:
    raw = f"{element_type}|{bbox[0]}|{bbox[1]}|{bbox[2]}|{bbox[3]}|{text.strip().lower()}"
    digest = hashlib.md5(raw.encode("utf-8")).hexdigest()[:12]
    return f"{element_type}_{digest}"


def _build_description(text_joined: str, n_text: int, n_btn: int) -> str:
    if text_joined:
        return (
            f"Screen contains {n_text} text block(s) and {n_btn} button candidate(s). "
            f"Visible text (partial): {text_joined[:300]}"
        )
    return (
        f"Screen contains no readable text. "
        f"Detected {n_btn} button candidate(s) via contour analysis."
    )



def analyze_frame_typed(img: np.ndarray, region: dict | None = None) -> ScreenState:
    """
    Analyzes a BGR screen frame and returns typed ScreenState.
    This is the new baseline path for the queue-based runtime.
    """
    elements: list[ScreenElement] = []
    all_text_parts: list[str] = []

    ocr_results = _reader.readtext(img)
    for (bbox_points, text, confidence) in ocr_results:
        cleaned = text.strip()
        if not cleaned:
            continue

        bbox = _bbox_from_points(bbox_points)
        all_text_parts.append(cleaned)
        elements.append(
            ScreenElement(
                type="text_block",
                bbox=bbox,
                text=cleaned,
                confidence=round(float(confidence), 3),
                element_id=_make_element_id("text_block", bbox, cleaned),
                source="easyocr",
                metadata={
                    "source_pass": "ocr",
                    "char_count": len(cleaned),
                },
            )
        )

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blurred, threshold1=50, threshold2=150)
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    img_area = img.shape[0] * img.shape[1]
    for cnt in contours:
        x, y, w, h = cv2.boundingRect(cnt)
        area = w * h
        if area < 800 or area > img_area * 0.6:
            continue

        aspect = w / h if h > 0 else 0
        if 1.5 <= aspect <= 10 and 10 <= h <= 80:
            bbox = [x, y, w, h]
            elements.append(
                ScreenElement(
                    type="button_candidate",
                    bbox=bbox,
                    text="",
                    confidence=0.0,
                    element_id=_make_element_id("button_candidate", bbox),
                    source="opencv_contour",
                    metadata={
                        "source_pass": "contour",
                        "area": area,
                        "aspect_ratio": round(float(aspect), 3),
                    },
                )
            )

    text_joined = " ".join(all_text_parts).strip()
    n_text = sum(1 for e in elements if e.type == "text_block")
    n_btn = sum(1 for e in elements if e.type == "button_candidate")
    description = _build_description(text_joined, n_text, n_btn)

    metadata = {
        "frame_width": int(img.shape[1]),
        "frame_height": int(img.shape[0]),
        "text_block_count": n_text,
        "button_candidate_count": n_btn,
        "total_element_count": len(elements),
        "ocr_language": ["en"],
        "pipeline": ["easyocr", "opencv_contour"],
    }

    return ScreenState(
        description=description,
        elements=elements,
        text=text_joined,
        timestamp=time.time(),
        region=region,
        active_window="",
        metadata=metadata,
    )



def analyze_frame(img: np.ndarray) -> dict:
    """
    Legacy compatibility wrapper.
    Returns the original dict format expected by older callers.
    """
    return analyze_frame_typed(img=img, region=None).to_legacy()



def get_screen_state_typed(region: dict | None = None) -> ScreenState:
    """
    Convenience wrapper: captures screen then analyzes it in one call.
    Returns typed ScreenState for new runtime code.
    """
    img = capture_screen(region)
    return analyze_frame_typed(img=img, region=region)



def get_screen_state(region: dict | None = None) -> dict:
    """
    Legacy compatibility wrapper: captures screen then returns the original dict format.
    """
    return get_screen_state_typed(region=region).to_legacy()
