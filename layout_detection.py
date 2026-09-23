from __future__ import annotations

from dataclasses import dataclass
import fitz
import cv2
import numpy as np
from PIL import Image


@dataclass
class LayoutBlock:
    page_index: int
    bbox: tuple[float, float, float, float]
    kind: str
    text: str = ""
    confidence: float = 1.0


def _native_blocks(page: fitz.Page, page_index: int) -> list[LayoutBlock]:
    blocks = []
    page_h = page.rect.height
    for block in page.get_text("dict").get("blocks", []):
        bbox = tuple(float(v) for v in block.get("bbox", (0, 0, 0, 0)))
        if block.get("type") == 1:
            blocks.append(LayoutBlock(page_index, bbox, "image", confidence=0.98))
            continue
        lines = block.get("lines", [])
        spans = [span for line in lines for span in line.get("spans", [])]
        text = " ".join(str(s.get("text", "")).strip() for s in spans if str(s.get("text", "")).strip())
        if not text:
            continue
        max_size = max((float(s.get("size", 0)) for s in spans), default=0)
        y0, y1 = bbox[1], bbox[3]
        if y0 < page_h * 0.10:
            kind = "header"
        elif y1 > page_h * 0.92:
            kind = "footer"
        elif max_size >= 16:
            kind = "heading"
        elif len(text) <= 45 and text.endswith((':', '?')):
            kind = "field-label"
        else:
            kind = "text"
        blocks.append(LayoutBlock(page_index, bbox, kind, text, 0.96))
    return blocks


def _cv_blocks(image: Image.Image, page_index: int, pdf_size: tuple[float, float]) -> list[LayoutBlock]:
    arr = np.asarray(image.convert("RGB"))
    gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
    bw = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY_INV, 31, 15)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (25, 5))
    merged = cv2.morphologyEx(bw, cv2.MORPH_CLOSE, kernel)
    contours, _ = cv2.findContours(merged, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    h, w = gray.shape
    pw, ph = pdf_size
    out = []
    for contour in contours:
        x, y, cw, ch = cv2.boundingRect(contour)
        if cw * ch < 900 or cw < 35 or ch < 8:
            continue
        bbox = (x * pw / w, y * ph / h, (x + cw) * pw / w, (y + ch) * ph / h)
        out.append(LayoutBlock(page_index, bbox, "visual-region", confidence=0.55))
    out.sort(key=lambda b: (b.bbox[1], b.bbox[0]))
    return out[:80]


def detect_layout(doc: fitz.Document, page_index: int, rendered_page: Image.Image | None = None) -> list[LayoutBlock]:
    page = doc[page_index]
    native = _native_blocks(page, page_index)
    if native:
        return native
    if rendered_page is None:
        pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False)
        rendered_page = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    return _cv_blocks(rendered_page, page_index, (page.rect.width, page.rect.height))
