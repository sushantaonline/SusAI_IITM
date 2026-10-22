
"""
RAG pipeline for ProcureAI.

Responsibilities:
1. Split supplier proposals into traceable chunks.
2. Preserve supplier, source, and page metadata.
3. Retrieve relevant evidence for individual RFP criteria.
"""

from pathlib import Path

import chromadb
from langchain_text_splitters import RecursiveCharacterTextSplitter
from sentence_transformers import SentenceTransformer

from src.rfp_evaluator.config import DATA_DIR


# Use the same model and collection as the vector index builder.
MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
COLLECTION_NAME = "supplier_proposals"
CHROMA_DIR = DATA_DIR / "chroma_db"

# Load these lazily so importing this module does not immediately load the model.
_embedding_model = None
_chroma_collection = None


def chunk_document(
    document_text: str,
    source_filename: str,
    supplier_name: str,
    chunk_size: int = 1000,
    chunk_overlap: int = 150,
) -> list[dict]:
    """Split document text into chunks while preserving source metadata."""

    if not document_text or not document_text.strip():
        return []

    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than zero")

    if chunk_overlap < 0 or chunk_overlap >= chunk_size:
        raise ValueError(
            "chunk_overlap must be non-negative and smaller than chunk_size"
        )

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=len,
        add_start_index=True,
    )

    chunks = splitter.create_documents(
        texts=[document_text],
        metadatas=[
            {
                "source_filename": source_filename,
                "supplier_name": supplier_name,
            }
        ],
    )

    return [
        {
            "chunk_id": f"{source_filename}:{index}",
            "text": chunk.page_content,
            "metadata": {
                **chunk.metadata,
                "chunk_index": index,
            },
        }
        for index, chunk in enumerate(chunks)
    ]


def chunk_pages(
    pages: list[dict],
    source_filename: str,
    supplier_name: str,
    chunk_size: int = 1000,
    chunk_overlap: int = 150,
) -> list[dict]:
    """Chunk page-level PDF text while preserving original page numbers."""

    all_chunks = []

    for page in pages:
        page_number = page["page_number"]

        page_chunks = chunk_document(
            document_text=page["text"],
            source_filename=source_filename,
            supplier_name=supplier_name,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )

        for chunk in page_chunks:
            chunk["chunk_id"] = (
                f"{source_filename}:page-{page_number}:"
                f"chunk-{chunk['metadata']['chunk_index']}"
            )
            chunk["metadata"]["page_number"] = page_number
            all_chunks.append(chunk)

    return all_chunks


def _get_embedding_model():
    """Load the embedding model only when retrieval is first requested."""

    global _embedding_model

    if _embedding_model is None:
        _embedding_model = SentenceTransformer(MODEL_NAME)

    return _embedding_model


def _get_chroma_collection():
    """Open the persistent collection created by build_vector_store.py."""

    global _chroma_collection

    if _chroma_collection is None:
        if not Path(CHROMA_DIR).exists():
            raise FileNotFoundError(
                f"Chroma index not found at {CHROMA_DIR}. "
                "Run python build_vector_store.py first."
            )

        client = chromadb.PersistentClient(path=str(CHROMA_DIR))

        try:
            _chroma_collection = client.get_collection(COLLECTION_NAME)
        except Exception as exc:
            raise RuntimeError(
                f"Chroma collection '{COLLECTION_NAME}' is unavailable. "
                "Run python build_vector_store.py first."
            ) from exc

    return _chroma_collection


def retrieve_evidence(
    supplier_name: str,
    criterion_name: str,
    criterion_description: str,
    top_k: int = 3,
) -> list[dict]:
    """
    Retrieve evidence for one supplier and one RFP criterion.

    Supplier filtering prevents evidence from other suppliers being
    passed into this supplier's evaluation.
    """

    if top_k <= 0:
        raise ValueError("top_k must be greater than zero")

    query = (
        f"RFP criterion: {criterion_name}. "
        f"Evaluation requirements: {criterion_description}"
    )

    model = _get_embedding_model()
    query_vector = model.encode(
        query,
        normalize_embeddings=True,
    ).tolist()

    collection = _get_chroma_collection()

    results = collection.query(
        query_embeddings=[query_vector],
        n_results=top_k,
        where={"supplier_name": supplier_name},
        include=["documents", "metadatas", "distances"],
    )

    evidence = []

    for index, document in enumerate(results["documents"][0]):
        metadata = results["metadatas"][0][index]

        evidence.append(
            {
                "text": document,
                "source_filename": metadata.get("source_filename", ""),
                "supplier_name": metadata.get("supplier_name", ""),
                "page_number": metadata.get("page_number"),
                "chunk_id": metadata.get("chunk_id", ""),
                "cosine_distance": results["distances"][0][index],
            }
        )

    return evidence
