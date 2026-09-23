from __future__ import annotations

from dataclasses import dataclass
import fitz


@dataclass(frozen=True)
class TextStyle:
    family: str
    fontname: str
    size: float
    color: tuple[float, float, float]
    bold: bool = False
    italic: bool = False


def int_color_to_rgb(color: int | None) -> tuple[float, float, float]:
    if color is None:
        return (0.0, 0.0, 0.0)
    return (((color >> 16) & 255) / 255.0, ((color >> 8) & 255) / 255.0, (color & 255) / 255.0)


def normalize_font(font_name: str | None) -> str:
    name = (font_name or "").lower().replace(" ", "")
    bold = any(t in name for t in ("bold", "black", "semibold", "demi"))
    italic = any(t in name for t in ("italic", "oblique"))
    if "cour" in name or "mono" in name:
        base = "cour"
    elif "times" in name or "serif" in name or "roman" in name:
        base = "times"
    else:
        base = "helv"
    if base == "helv":
        if bold and italic: return "helv-bi"
        if bold: return "helv-b"
        if italic: return "helv-i"
        return "helv"
    if base == "times":
        if bold and italic: return "times-bolditalic"
        if bold: return "times-bold"
        if italic: return "times-italic"
        return "times-roman"
    if bold and italic: return "cour-bi"
    if bold: return "cour-b"
    if italic: return "cour-i"
    return "cour"


def style_from_span(span: dict) -> TextStyle:
    raw = str(span.get("font", "Helvetica"))
    low = raw.lower()
    return TextStyle(
        family=raw,
        fontname=normalize_font(raw),
        size=float(span.get("size", 10.0)),
        color=int_color_to_rgb(span.get("color")),
        bold=any(t in low for t in ("bold", "black", "semibold", "demi")),
        italic=any(t in low for t in ("italic", "oblique")),
    )


def fit_font_size(text: str, fontname: str, initial_size: float, max_width: float, min_size: float = 4.0) -> float:
    size = max(min_size, float(initial_size))
    while size > min_size:
        try:
            if fitz.get_text_length(text, fontname=fontname, fontsize=size) <= max_width:
                return size
        except Exception:
            if len(text) * size * 0.55 <= max_width:
                return size
        size -= 0.25
    return min_size


def style_summary(font: str, size: float, color: tuple[float, float, float]) -> str:
    rgb = tuple(round(v * 255) for v in color)
    return f"{font} · {size:.1f} pt · rgb{rgb}"
