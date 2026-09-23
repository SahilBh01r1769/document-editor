# Document Editor

A small Streamlit utility for making controlled text edits to PDFs.

It started as a simple region-based PDF text replacer and now includes a few document-analysis helpers. This is mainly a practical side tool, not an attempt to be a full PDF editor.

## What it does

- upload and preview PDFs
- find exact text or draw a rectangle around a region
- use native PDF text when available
- fall back to OCR for scanned/image-based regions
- replace or remove text
- queue edits across multiple pages
- preserve font size, family/style and color where possible
- preprocess difficult OCR regions and choose the strongest result
- detect basic page layout regions
- save/reapply edit templates
- classify selected text such as dates, numbers, IDs, emails and short labels
- verify rendered changes outside selected regions

## Run

```bash
python -m venv .venv
pip install -r requirements.txt
streamlit run app.py
```

OCR uses Tesseract. If it is not available on PATH, set `TESSERACT_CMD` before starting the app.

## Notes

PDF editing is inconsistent across files. Text-based PDFs usually behave better than scanned documents. For scanned pages the app estimates the local background before replacing text, but textured backgrounds and unusual fonts can still require manual review.

Layout detection is deliberately lightweight: it uses the PDF text structure first and OpenCV grouping as a fallback rather than introducing a large document model.

## Files

```text
app.py
editor.py
style_matching.py
ocr_engine.py
layout_detection.py
templates.py
region_understanding.py
requirements.txt
```
