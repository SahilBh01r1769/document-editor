from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional
import io
import os

import fitz
import numpy as np
from PIL import Image
import pytesseract


TESSERACT_CMD = os.getenv("TESSERACT_CMD")
if TESSERACT_CMD:
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD


@dataclass
class Selection:
    page_index: int
    bbox: tuple[float, float, float, float]
    original_text: str
    source: str
    font: str = "helv"
    font_size: float = 10.0
    color: tuple[float, float, float] = (0.0, 0.0, 0.0)
    origin: Optional[tuple[float, float]] = None


@dataclass
class Edit:
    selection: Selection
    operation: str
    replacement: str = ""


def open_pdf(pdf_bytes: bytes) -> fitz.Document:
    return fitz.open(stream=pdf_bytes, filetype="pdf")


def render_page(doc: fitz.Document, page_index: int, dpi: int = 150) -> Image.Image:
    page = doc[page_index]
    pix = page.get_pixmap(matrix=fitz.Matrix(dpi / 72.0, dpi / 72.0), alpha=False)
    return Image.frombytes("RGB", [pix.width, pix.height], pix.samples)


def page_size(doc: fitz.Document, page_index: int) -> tuple[float, float]:
    rect = doc[page_index].rect
    return float(rect.width), float(rect.height)


def image_bbox_to_pdf_bbox(image_bbox, image_size, pdf_size):
    x0, y0, x1, y1 = image_bbox
    iw, ih = image_size
    pw, ph = pdf_size
    return x0 * pw / iw, y0 * ph / ih, x1 * pw / iw, y1 * ph / ih


def pdf_bbox_to_image_bbox(pdf_bbox, image_size, pdf_size):
    x0, y0, x1, y1 = pdf_bbox
    iw, ih = image_size
    pw, ph = pdf_size
    return (
        int(round(x0 * iw / pw)),
        int(round(y0 * ih / ph)),
        int(round(x1 * iw / pw)),
        int(round(y1 * ih / ph)),
    )


def _rgb(color: int | None):
    if color is None:
        return (0.0, 0.0, 0.0)
    return (((color >> 16) & 255) / 255, ((color >> 8) & 255) / 255, (color & 255) / 255)


def native_text_spans(page: fitz.Page) -> list[dict]:
    spans = []
    for block in page.get_text("dict").get("blocks", []):
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                if span.get("text", "").strip():
                    spans.append(span)
    return spans


def search_text(doc: fitz.Document, query: str) -> list[Selection]:
    query = query.strip()
    if not query:
        return []
    out = []
    for page_index, page in enumerate(doc):
        spans = native_text_spans(page)
        for rect in page.search_for(query):
            best = None
            overlap = 0.0
            for span in spans:
                area = (rect & fitz.Rect(span["bbox"])).get_area()
                if area > overlap:
                    overlap = area
                    best = span
            if best:
                origin = best.get("origin", (rect.x0, rect.y1))
                out.append(Selection(
                    page_index,
                    (rect.x0, rect.y0, rect.x1, rect.y1),
                    query,
                    "native",
                    best.get("font", "helv"),
                    float(best.get("size", 10.0)),
                    _rgb(best.get("color")),
                    (float(origin[0]), float(origin[1])),
                ))
            else:
                out.append(Selection(page_index, tuple(rect), query, "native"))
    return out


def select_region(doc, page_index, bbox, ocr_if_needed=True, ocr_dpi=220):
    page = doc[page_index]
    rect = fitz.Rect(*bbox)
    hits = [s for s in native_text_spans(page) if (rect & fitz.Rect(s["bbox"])).get_area() > 0]
    if hits:
        hits.sort(key=lambda s: (s["bbox"][1], s["bbox"][0]))
        main = max(hits, key=lambda s: len(s.get("text", "")))
        origin = main.get("origin", (rect.x0, rect.y1))
        return Selection(
            page_index,
            bbox,
            " ".join(s["text"].strip() for s in hits if s["text"].strip()),
            "native",
            main.get("font", "helv"),
            float(main.get("size", 10.0)),
            _rgb(main.get("color")),
            (float(origin[0]), float(origin[1])),
        )
    if not ocr_if_needed:
        return Selection(page_index, bbox, "", "region")
    page_img = render_page(doc, page_index, dpi=ocr_dpi)
    crop = page_img.crop(pdf_bbox_to_image_bbox(bbox, page_img.size, page_size(doc, page_index)))
    text = pytesseract.image_to_string(crop, config="--psm 6").strip()
    return Selection(page_index, bbox, text, "ocr", font_size=max(8.0, min(20.0, rect.height * 0.75)))


def _font_alias(name: str) -> str:
    n = (name or "").lower()
    if "cour" in n:
        return "cour"
    if "times" in n or "roman" in n:
        return "times-roman"
    return "helv"


def _fit_size(text: str, font: str, size: float, width: float) -> float:
    size = max(4.0, size)
    while size > 4.0:
        try:
            if fitz.get_text_length(text, fontname=font, fontsize=size) <= width:
                return size
        except Exception:
            if len(text) * size * 0.55 <= width:
                return size
        size -= 0.25
    return 4.0


def _background(page: fitz.Page, rect: fitz.Rect):
    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    crop = np.asarray(img.crop(pdf_bbox_to_image_bbox(tuple(rect), img.size, (page.rect.width, page.rect.height))))
    if crop.size == 0:
        return (1.0, 1.0, 1.0)
    border = np.concatenate([
        crop[:max(1, crop.shape[0] // 8)].reshape(-1, 3),
        crop[-max(1, crop.shape[0] // 8):].reshape(-1, 3),
        crop[:, :max(1, crop.shape[1] // 8)].reshape(-1, 3),
        crop[:, -max(1, crop.shape[1] // 8):].reshape(-1, 3),
    ])
    return tuple((np.median(border, axis=0) / 255.0).tolist())


def apply_edits(pdf_bytes: bytes, edits: Iterable[Edit]) -> bytes:
    doc = open_pdf(pdf_bytes)
    edits = list(edits)
    for edit in edits:
        page = doc[edit.selection.page_index]
        rect = fitz.Rect(*edit.selection.bbox)
        page.add_redact_annot(rect, fill=_background(page, rect) if edit.selection.source == "ocr" else (1, 1, 1))
    for page_index in sorted({e.selection.page_index for e in edits}):
        doc[page_index].apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE)

    for edit in edits:
        if edit.operation != "replace" or not edit.replacement:
            continue
        s = edit.selection
        page = doc[s.page_index]
        rect = fitz.Rect(*s.bbox)
        font = _font_alias(s.font)
        size = _fit_size(edit.replacement, font, s.font_size, max(4.0, rect.width))
        baseline = s.origin[1] if s.origin else rect.y1 - 1
        baseline = min(max(baseline, rect.y0 + size), rect.y1 + size * 0.25)
        page.insert_text(fitz.Point(rect.x0, baseline), edit.replacement, fontsize=size, fontname=font, color=s.color, overlay=True)

    out = io.BytesIO()
    doc.save(out, garbage=4, deflate=True)
    doc.close()
    return out.getvalue()


def verification_report(original_pdf, edited_pdf, edits, dpi=150):
    original = open_pdf(original_pdf)
    edited = open_pdf(edited_pdf)
    by_page = {}
    for edit in edits:
        by_page.setdefault(edit.selection.page_index, []).append(edit.selection.bbox)
    report = []
    for page_index in range(min(len(original), len(edited))):
        a = np.asarray(render_page(original, page_index, dpi=dpi))
        b = np.asarray(render_page(edited, page_index, dpi=dpi))
        diff = np.any(a != b, axis=2)
        allowed = np.zeros(diff.shape, dtype=bool)
        for bbox in by_page.get(page_index, []):
            x0, y0, x1, y1 = pdf_bbox_to_image_bbox(
                bbox,
                (a.shape[1], a.shape[0]),
                (original[page_index].rect.width, original[page_index].rect.height),
            )
            x0, y0 = max(0, x0 - 3), max(0, y0 - 3)
            x1, y1 = min(allowed.shape[1], x1 + 3), min(allowed.shape[0], y1 + 3)
            allowed[y0:y1, x0:x1] = True
        outside = diff & ~allowed
        report.append({
            "page": page_index + 1,
            "outside_changed_pixels": int(outside.sum()),
            "total_changed_pixels": int(diff.sum()),
            "status": "ok" if not outside.any() else "review",
        })
    original.close()
    edited.close()
    return report
