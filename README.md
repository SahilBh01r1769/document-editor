# Document Editor

Small Streamlit utility for controlled PDF text edits.

Current scope:
- upload and preview PDFs
- select text by search or a drawn rectangle
- use native PDF text when available and OCR otherwise
- queue multiple replace/remove edits
- export an edited PDF
- verify that rendered changes stay inside selected regions

## Run

```bash
python -m venv .venv
pip install -r requirements.txt
streamlit run app.py
```

OCR uses Tesseract. Set `TESSERACT_CMD` if it is not available on PATH.
