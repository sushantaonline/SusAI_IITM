
"""Validate page-aware chunking against all local supplier PDFs."""

from pathlib import Path

import pymupdf

from src.rfp_evaluator.config import INPUT_DIR
from src.rfp_evaluator.rag_pipeline import chunk_pages


def main():
    pdf_files = sorted(INPUT_DIR.glob("*.pdf"))

    if not pdf_files:
        print(f"No PDFs found in: {INPUT_DIR}")
        return

    total_chunks = 0

    for pdf_path in pdf_files:
        # Extract each PDF page separately to preserve page numbers.
        with pymupdf.open(pdf_path) as document:
            pages = [
                {
                    "page_number": page_number,
                    "text": page.get_text(),
                }
                for page_number, page in enumerate(document, start=1)
            ]

        # Infer the supplier name from the filename for this first test.
        supplier_name = pdf_path.stem.split("_rfp_response")[0]

        chunks = chunk_pages(
            pages=pages,
            source_filename=pdf_path.name,
            supplier_name=supplier_name,
        )

        total_chunks += len(chunks)

        print(
            f"{pdf_path.name}: "
            f"{len(pages)} pages, {len(chunks)} chunks"
        )

        # Show one sample chunk so we can verify its metadata.
        if chunks:
            print("  Sample metadata:", chunks[0]["metadata"])
        else:
            print("  WARNING: No text extracted from this PDF.")

    print(f"\nPDFs processed: {len(pdf_files)}")
    print(f"Total chunks created: {total_chunks}")


if __name__ == "__main__":
    main()
