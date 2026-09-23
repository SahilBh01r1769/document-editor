from __future__ import annotations

import streamlit as st
from streamlit_drawable_canvas import st_canvas

from layout_detection import detect_layout
from templates import build_template, dumps_template, loads_template, apply_template
from style_matching import style_summary

from editor import (
    Edit,
    apply_edits,
    image_bbox_to_pdf_bbox,
    open_pdf,
    page_size,
    render_page,
    search_text,
    select_region,
    verification_report,
)

st.set_page_config(page_title="Document Editor", layout="wide")
st.title("Document Editor")
st.caption("Controlled PDF text edits with local-region verification.")

if "edits" not in st.session_state:
    st.session_state.edits = []
if "search_results" not in st.session_state:
    st.session_state.search_results = []

uploaded = st.file_uploader("Upload a PDF", type=["pdf"])
if not uploaded:
    st.info("Upload a PDF to begin.")
    st.stop()

pdf_bytes = uploaded.getvalue()
doc = open_pdf(pdf_bytes)

left, right = st.columns([0.36, 0.64], gap="large")

with left:
    page_number = st.number_input("Page", 1, len(doc), 1)
    page_index = int(page_number) - 1

    mode = st.radio("Select content", ["Search text", "Draw rectangle"], horizontal=True)
    pending = None

    if mode == "Search text":
        query = st.text_input("Exact text")
        if st.button("Find text", use_container_width=True):
            st.session_state.search_results = search_text(doc, query)

        results = st.session_state.search_results
        if results:
            idx = st.selectbox(
                "Match",
                range(len(results)),
                format_func=lambda i: (
                    f"Page {results[i].page_index + 1} — "
                    f"{results[i].original_text!r}"
                ),
            )
            pending = results[idx]

        if pending:
            st.write(f"Detected: `{pending.original_text}`")
            st.caption(f"Source: {pending.source}")
            st.caption(f"Style: {style_summary(pending.font, pending.font_size, pending.color)}")
            operation = st.radio("Operation", ["replace", "remove"], horizontal=True, key="search_op")
            replacement = st.text_input("Replacement", key="search_replacement") if operation == "replace" else ""
            if st.button("Add edit", use_container_width=True):
                st.session_state.edits.append(Edit(pending, operation, replacement))
                st.success("Edit added.")

    st.subheader("Detected layout")
    if st.button("Analyze page layout", use_container_width=True):
        st.session_state.layout_blocks = detect_layout(doc, page_index, render_page(doc, page_index, dpi=150))

    blocks = [b for b in st.session_state.get("layout_blocks", []) if b.page_index == page_index]
    if blocks:
        labels = [f"{i+1}. {b.kind} — {b.text[:45] or 'region'}" for i, b in enumerate(blocks)]
        chosen = st.selectbox("Detected region", range(len(blocks)), format_func=lambda i: labels[i])
        block = blocks[chosen]
        st.caption(f"Box: {tuple(round(v, 1) for v in block.bbox)} · confidence {block.confidence:.0%}")
        if st.button("Use detected region", use_container_width=True):
            st.session_state.region_selection = select_region(doc, page_index, block.bbox, ocr_if_needed=True)
            st.success("Detected region loaded into the edit controls.")

    st.subheader("Queued edits")
    if not st.session_state.edits:
        st.caption("No edits queued.")
    for i, edit in enumerate(st.session_state.edits):
        s = edit.selection
        with st.expander(f"{i+1}. Page {s.page_index+1} — {edit.operation} — {s.original_text!r}"):
            st.write({
                "bbox": [round(v, 2) for v in s.bbox],
                "source": s.source,
                "replacement": edit.replacement,
            })
            if st.button("Remove", key=f"remove_{i}"):
                st.session_state.edits.pop(i)
                st.rerun()

    if st.session_state.edits and st.button("Clear queue", use_container_width=True):
        st.session_state.edits = []
        st.rerun()

    st.subheader("Templates")
    template_name = st.text_input("Template name", value="Document template")
    if st.session_state.edits:
        template_payload = dumps_template(build_template(template_name, doc, st.session_state.edits))
        st.download_button(
            "Save current edits as template",
            data=template_payload,
            file_name="pdf_edit_template.json",
            mime="application/json",
            use_container_width=True,
        )

    template_file = st.file_uploader("Load template", type=["json"], key="template_upload")
    if template_file and st.button("Apply template to this PDF", use_container_width=True):
        try:
            template = loads_template(template_file.getvalue())
            st.session_state.edits.extend(apply_template(doc, template))
            st.success(f"Loaded {len(template.get('edits', []))} template edits.")
            st.rerun()
        except Exception as e:
            st.error(f"Could not load template: {e}")

with right:
    preview = render_page(doc, page_index, dpi=150)
    st.subheader("Page preview")

    if mode == "Draw rectangle":
        display_w = min(900, preview.width)
        scale = display_w / preview.width
        display_h = int(preview.height * scale)
        canvas = st_canvas(
            fill_color="rgba(255, 0, 0, 0.08)",
            stroke_width=2,
            stroke_color="#d33",
            background_image=preview.resize((display_w, display_h)),
            update_streamlit=True,
            height=display_h,
            width=display_w,
            drawing_mode="rect",
            key=f"canvas_{page_index}",
        )

        if canvas.json_data and canvas.json_data.get("objects"):
            obj = canvas.json_data["objects"][-1]
            x0 = float(obj.get("left", 0))
            y0 = float(obj.get("top", 0))
            x1 = x0 + float(obj.get("width", 0)) * float(obj.get("scaleX", 1))
            y1 = y0 + float(obj.get("height", 0)) * float(obj.get("scaleY", 1))
            bbox = image_bbox_to_pdf_bbox(
                (x0, y0, x1, y1),
                (display_w, display_h),
                page_size(doc, page_index),
            )

            if st.button("Recognize selected region", use_container_width=True):
                st.session_state.region_selection = select_region(doc, page_index, bbox)

            region = st.session_state.get("region_selection")
            if region and region.page_index == page_index:
                st.write(f"Detected text: `{region.original_text}`")
                st.caption(f"Source: {region.source}")
                st.caption(f"Style: {style_summary(region.font, region.font_size, region.color)}")
                operation = st.radio("Region operation", ["replace", "remove"], horizontal=True)
                replacement = st.text_input("Region replacement") if operation == "replace" else ""
                if st.button("Add region edit", use_container_width=True):
                    st.session_state.edits.append(Edit(region, operation, replacement))
                    st.success("Edit added.")
        else:
            st.caption("Draw a rectangle around the text to edit.")
    else:
        st.image(preview, use_container_width=True)

st.divider()
st.subheader("Generate")

if st.session_state.edits and st.button("Generate edited PDF", type="primary"):
    output = apply_edits(pdf_bytes, st.session_state.edits)
    st.session_state.output_pdf = output
    st.session_state.report = verification_report(pdf_bytes, output, st.session_state.edits)

if "output_pdf" in st.session_state:
    st.download_button(
        "Download edited PDF",
        st.session_state.output_pdf,
        file_name="edited_document.pdf",
        mime="application/pdf",
        use_container_width=True,
    )
    st.subheader("Verification")
    for row in st.session_state.get("report", []):
        message = (
            f"Page {row['page']}: {row['outside_changed_pixels']} changed pixels "
            "outside selected regions."
        )
        if row["status"] == "ok":
            st.success(message)
        else:
            st.warning(message)
