from __future__ import annotations

import json
from editor import Edit, Selection, page_size, search_text

TEMPLATE_VERSION = 1


def build_template(name: str, doc, edits: list[Edit]) -> dict:
    items = []
    for edit in edits:
        s = edit.selection
        pw, ph = page_size(doc, s.page_index)
        x0, y0, x1, y1 = s.bbox
        items.append({
            "page_index": s.page_index,
            "bbox_norm": [x0 / pw, y0 / ph, x1 / pw, y1 / ph],
            "anchor_text": s.original_text if s.source == "native" else "",
            "operation": edit.operation,
            "replacement": edit.replacement,
            "font": s.font,
            "font_size": s.font_size,
            "color": list(s.color),
        })
    return {"version": TEMPLATE_VERSION, "name": name.strip() or "Untitled template", "edits": items}


def dumps_template(template: dict) -> str:
    return json.dumps(template, indent=2)


def loads_template(raw: str | bytes) -> dict:
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    data = json.loads(raw)
    if data.get("version") != TEMPLATE_VERSION or not isinstance(data.get("edits"), list):
        raise ValueError("Unsupported template format")
    return data


def apply_template(doc, template: dict) -> list[Edit]:
    out: list[Edit] = []
    for item in template.get("edits", []):
        page_index = int(item["page_index"])
        if page_index >= len(doc):
            continue
        selection = None
        anchor = str(item.get("anchor_text", "")).strip()
        if anchor:
            matches = [m for m in search_text(doc, anchor) if m.page_index == page_index]
            if matches:
                selection = matches[0]
        if selection is None:
            pw, ph = page_size(doc, page_index)
            x0, y0, x1, y1 = item["bbox_norm"]
            selection = Selection(
                page_index=page_index,
                bbox=(x0 * pw, y0 * ph, x1 * pw, y1 * ph),
                original_text=anchor,
                source="template",
                font=item.get("font", "helv"),
                font_size=float(item.get("font_size", 10.0)),
                color=tuple(item.get("color", [0.0, 0.0, 0.0])),
            )
        out.append(Edit(selection, item.get("operation", "replace"), item.get("replacement", "")))
    return out
