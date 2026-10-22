
"""Test local embedding generation for ProcureAI."""

from sentence_transformers import SentenceTransformer

# Load a lightweight, open-source embedding model.
model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")

# Sample procurement evidence.
texts = [
    "The supplier provides AES-256 encryption and audit logging.",
    "The supplier offers a five-year implementation support plan.",
]

# Convert text into numerical vectors.
embeddings = model.encode(texts)

print("Number of texts:", len(texts))
print("Embedding dimensions:", embeddings.shape[1])
print("First vector sample:", embeddings[0][:5])
