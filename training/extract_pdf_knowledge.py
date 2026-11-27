"""Extract user-provided PDF references into a reviewable knowledge-base file.

This script does not train a visual model or turn PDF text into trading signals.
It preserves extracted source text with page numbers for later human curation.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from pypdf import PdfReader


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="knowledge/pdfs")
    parser.add_argument("--out", default="knowledge/pdf_knowledge.json")
    args = parser.parse_args()

    root = Path(args.input)
    if not root.exists():
        raise SystemExit(f"PDF folder not found: {root}")
    documents = []
    errors = []
    for pdf in sorted(root.glob("*.pdf")):
        try:
            reader = PdfReader(str(pdf), strict=False)
            pages = []
            for number, page in enumerate(reader.pages, 1):
                text = (page.extract_text() or "").strip()
                if text:
                    pages.append({"page": number, "text": text})
            if not pages:
                errors.append({"file": pdf.name, "error": "No extractable text; OCR or a readable source is required."})
                continue
            documents.append({
                "source_file": pdf.name,
                "page_count": len(reader.pages),
                "pages": pages,
            })
        except Exception as exc:
            errors.append({"file": pdf.name, "error": str(exc)[:300]})

    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({
        "schema_version": 1,
        "purpose": "Reference material for human-reviewed pattern definitions",
        "documents": documents,
        "errors": errors,
        "warning": "Extracted text is reference material, not model labels, a prediction target, or evidence of trading profitability."
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Extracted {len(documents)} PDFs; {len(errors)} require repair/OCR. Wrote {output}")


if __name__ == "__main__":
    main()
