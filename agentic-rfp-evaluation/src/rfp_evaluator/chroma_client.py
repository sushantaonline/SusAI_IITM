"""Shared ChromaDB client configured for reliable local persistence."""

import chromadb
from chromadb.config import Settings

from src.rfp_evaluator.config import DATA_DIR


CHROMA_DIR = (DATA_DIR / "chroma_db").resolve()

# Keep one client/system per Streamlit process. Streamlit reruns the app script,
# but imported modules remain cached in sys.modules.
_client = None


def get_chroma_client():
    """Return the process-wide persistent client using Chroma's Python API."""

    global _client

    if _client is None:
        settings = Settings(
            chroma_api_impl="chromadb.api.segment.SegmentAPI",
        )
        _client = chromadb.PersistentClient(
            path=str(CHROMA_DIR),
            settings=settings,
        )

    return _client
