
"""
Build a persistent local Chroma vector index for ProcureAI.

Workflow:
1. Load the local embedding model.
2. Extract text from each supplier PDF page by page.
3. Split the text into chunks with source metadata.
4. Generate embeddings for each chunk.
5. Store chunks and vectors in Chroma.
"""

import pymupdf
from sentence_transformers import SentenceTransformer

from src.rfp_evaluator.config import DATA_DIR, INPUT_DIR
from src.rfp_evaluator.rag_pipeline import chunk_pages
from src.rfp_evaluator.chroma_client import get_chroma_client


# Local directory for persistent vector storage.
CHROMA_DIR = DATA_DIR / "chroma_db"

# Name of the Chroma collection.
COLLECTION_NAME = "supplier_proposals"

# Lightweight, locally executed embedding model.
MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"


def build_vector_store(client=None):
    """Build/rebuild the proposal index, optionally using an existing client."""

    # Load the embedding model from the local Hugging Face cache.
    model = SentenceTransformer(MODEL_NAME)

    # Reuse the app client when called by Streamlit; otherwise use the shared one.
    if client is None:
        client = get_chroma_client()

    # Delete the previous collection only if it exists.
    existing_collections = [
        item.name for item in client.list_collections()
    ]

    if COLLECTION_NAME in existing_collections:
        client.delete_collection(COLLECTION_NAME)
        print("Deleted existing collection for rebuilding.")

    # Create a fresh collection for this indexing run.
    collection = client.create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )

    # Locate all supplier proposal PDFs.
    pdf_files = sorted(INPUT_DIR.glob("*.pdf"))

    if not pdf_files:
        raise FileNotFoundError(
            f"No supplier PDFs found in: {INPUT_DIR}"
        )

    total_chunks = 0
    processed_pdfs = 0

    for pdf_path in pdf_files:
        # Extract text separately for each page to preserve page numbers.
        with pymupdf.open(pdf_path) as document:
            pages = [
                {
                    "page_number": page_number,
                    "text": page.get_text(),
                }
                for page_number, page in enumerate(document, start=1)
            ]

        # Derive a supplier identifier from the PDF filename.
        supplier_name = pdf_path.stem.split("_rfp_response")[0]

        # Reuse the existing RAG chunking implementation.
        chunks = chunk_pages(
            pages=pages,
            source_filename=pdf_path.name,
            supplier_name=supplier_name,
        )

        if not chunks:
            print(f"WARNING: No text extracted from {pdf_path.name}")
            continue

        # Generate a 384-dimensional embedding for every chunk.
        texts = [chunk["text"] for chunk in chunks]

        vectors = model.encode(
            texts,
            normalize_embeddings=True,
            show_progress_bar=False,
        )

        # Chroma metadata supports strings, numbers, and booleans.
        metadatas = [
            {
                **chunk["metadata"],
                "chunk_id": chunk["chunk_id"],
            }
            for chunk in chunks
        ]

        # Store text, metadata, and vectors together.
        collection.add(
            ids=[chunk["chunk_id"] for chunk in chunks],
            documents=texts,
            embeddings=vectors.tolist(),
            metadatas=metadatas,
        )

        total_chunks += len(chunks)
        processed_pdfs += 1

        print(
            f"Indexed {pdf_path.name}: "
            f"{len(chunks)} chunks"
        )

    # Verify the final index.
    print("\nIndex build complete.")
    print("PDFs discovered:", len(pdf_files))
    print("PDFs processed:", processed_pdfs)
    print("Chunks generated:", total_chunks)
    print("Vectors stored:", collection.count())
    print("Chroma directory:", CHROMA_DIR)
    return collection


def main():
    build_vector_store()


if __name__ == "__main__":
    main()
