from __future__ import annotations

from dataclasses import dataclass
import os
import cv2
import numpy as np
import pytesseract
from PIL import Image


if os.getenv("TESSERACT_CMD"):
    pytesseract.pytesseract.tesseract_cmd = os.environ["TESSERACT_CMD"]


@dataclass
class OCRResult:
    text: str
    confidence: float
    preprocessing: str


def _variants(image: Image.Image):
    rgb = np.asarray(image.convert("RGB"))
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    gray = cv2.resize(gray, None, fx=1.7, fy=1.7, interpolation=cv2.INTER_CUBIC)
    denoised = cv2.fastNlMeansDenoising(gray, None, 12, 7, 21)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(denoised)
    adaptive = cv2.adaptiveThreshold(clahe, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 13)
    _, otsu = cv2.threshold(clahe, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return [("grayscale", gray), ("contrast", clahe), ("adaptive", adaptive), ("otsu", otsu)]


def _run(arr: np.ndarray, psm: int) -> OCRResult:
    data = pytesseract.image_to_data(arr, config=f"--oem 3 --psm {psm}", output_type=pytesseract.Output.DICT)
    words, confs = [], []
    for text, conf in zip(data.get("text", []), data.get("conf", [])):
        text = str(text).strip()
        try:
            conf = float(conf)
        except (TypeError, ValueError):
            conf = -1
        if text and conf >= 0:
            words.append(text)
            confs.append(conf)
    return OCRResult(" ".join(words).strip(), float(np.mean(confs)) if confs else 0.0, "")


def recognize_region(image: Image.Image) -> OCRResult:
    best = OCRResult("", 0.0, "none")
    for name, arr in _variants(image):
        for psm in (6, 7, 11):
            result = _run(arr, psm)
            score = result.confidence + min(len(result.text), 80) * 0.05
            best_score = best.confidence + min(len(best.text), 80) * 0.05
            if result.text and score > best_score:
                best = OCRResult(result.text, result.confidence, f"{name}/psm{psm}")
    return best
