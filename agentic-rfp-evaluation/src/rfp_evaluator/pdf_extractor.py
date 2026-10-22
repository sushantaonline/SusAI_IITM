
from pathlib import Path
import pymupdf


def extract_pdf_text(pdf_path: str | Path) -> str:
    """Extract text from a supplier's PDF proposal."""
    path = Path(pdf_path)

    if not path.exists():
        raise FileNotFoundError(f"PDF not found: {path}")

    if path.suffix.lower() != ".pdf":
        raise ValueError(f"Expected a PDF file: {path}")

    with pymupdf.open(path) as document:
        text = "\n".join(page.get_text() for page in document)

    if not text.strip():
        raise ValueError(
            f"No extractable text found in PDF: {path.name}. "
            "It may be a scanned document requiring OCR."
        )

    return text
