from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(frozen=True)
class RegionInsight:
    kind: str
    confidence: float
    reason: str
    suggested_actions: tuple[str, ...]


DATE_PATTERNS = [
    r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b",
    r"\b\d{4}[/-]\d{1,2}[/-]\d{1,2}\b",
]
EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)
PHONE_RE = re.compile(r"(?:\+?\d[\d\s().-]{7,}\d)")
AMOUNT_RE = re.compile(r"(?:₹|\$|€|£|Rs\.?\s*)?[-+]?\d[\d,]*(?:\.\d{1,2})?")
ID_RE = re.compile(r"\b(?=[A-Z0-9-]{6,}\b)(?=.*[A-Z])(?=.*\d)[A-Z0-9-]+\b", re.I)


def understand_region(text: str, source: str = "native") -> RegionInsight:
    value = " ".join((text or "").split()).strip()
    if not value:
        return RegionInsight("empty / visual region", 0.72, "No text was detected in the selected area.", ("remove", "inspect manually"))
    if EMAIL_RE.fullmatch(value):
        return RegionInsight("email", 0.98, "Matches a conventional email pattern.", ("replace", "remove"))
    if any(re.fullmatch(p, value) for p in DATE_PATTERNS):
        return RegionInsight("date", 0.96, "Matches a common numeric date format.", ("replace", "remove"))
    if PHONE_RE.fullmatch(value):
        return RegionInsight("phone number", 0.91, "Mostly numeric with phone-like separators and length.", ("replace", "remove"))
    if ID_RE.fullmatch(value):
        return RegionInsight("identifier", 0.88, "Contains a structured mix of letters and digits.", ("replace", "remove"))
    if AMOUNT_RE.fullmatch(value) and any(ch.isdigit() for ch in value):
        kind = "amount / number" if any(sym in value for sym in ("₹", "$", "€", "£", ",", ".")) else "number"
        return RegionInsight(kind, 0.90, "The region is predominantly numeric.", ("replace", "remove", "generate variants"))
    words = value.split()
    if 1 < len(words) <= 5 and all(re.fullmatch(r"[A-Za-z][A-Za-z'.-]*", w) for w in words):
        title_ratio = sum(w[:1].isupper() for w in words) / len(words)
        if title_ratio >= 0.75:
            return RegionInsight("name / short label", 0.76, "Short title-cased text; could be a name or field value.", ("replace", "remove"))
    if len(value) > 100 or len(words) > 18:
        return RegionInsight("paragraph", 0.86, "Long continuous text block.", ("replace", "remove"))
    if value.endswith(":") or value.endswith("?"):
        return RegionInsight("field label", 0.82, "Short text ending like a form label or prompt.", ("replace", "remove"))
    base_conf = 0.72 if source == "ocr" else 0.80
    return RegionInsight("text", base_conf, "General text without a stronger structural pattern.", ("replace", "remove"))
