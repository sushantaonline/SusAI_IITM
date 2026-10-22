
"""Inspect the top five semantic search results from Chroma."""

import chromadb
from sentence_transformers import SentenceTransformer

from src.rfp_evaluator.config import DATA_DIR


MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
COLLECTION_NAME = "supplier_proposals"

# Test query: security and compliance evidence.
QUERY = (
    "What encryption, identity access controls, "
    "and audit logging does the supplier provide?"
)


def main():
    # Reopen the locally persisted Chroma database.
    client = chromadb.PersistentClient(
        path=str(DATA_DIR / "chroma_db")
    )
    collection = client.get_collection(COLLECTION_NAME)

    # Load the local embedding model.
    model = SentenceTransformer(MODEL_NAME)

    # Convert the query into a vector.
    query_vector = model.encode(
        QUERY,
        normalize_embeddings=True,
    ).tolist()

    # Retrieve the five closest chunks across all suppliers.
    results = collection.query(
        query_embeddings=[query_vector],
        n_results=5,
        include=["documents", "metadatas", "distances"],
    )

    print("=" * 80)
    print("RAG SEMANTIC RETRIEVAL TEST")
    print("Query:", QUERY)
    print("Results returned:", len(results["documents"][0]))
    print("=" * 80)

    for index, document in enumerate(results["documents"][0]):
        metadata = results["metadatas"][0][index]
        distance = results["distances"][0][index]

        print(f"\nRESULT {index + 1}")
        print("-" * 80)
        print("Supplier:", metadata.get("supplier_name"))
        print("Source PDF:", metadata.get("source_filename"))
        print("Page:", metadata.get("page_number"))
        print("Chunk ID:", metadata.get("chunk_id"))
        print("Cosine distance:", round(distance, 4))
        print("\nFULL EVIDENCE:")
        print(document)

    print("\n" + "=" * 80)


if __name__ == "__main__":
    main()
