"""
search_docs — top-k similarity search against ChromaDB.
Returns chunk_id + score pairs for citations and tracing.
"""

import logging
from dataclasses import dataclass

import chromadb

from app.config import settings

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """A single search result with chunk content, ID, metadata, and distance score."""
    chunk_id: str
    content: str
    score: float  # cosine similarity score in [0, 1]
    metadata: dict[str, str]


def _get_collection() -> chromadb.Collection:
    """Get (or create) the ChromaDB collection."""
    client = chromadb.PersistentClient(path=settings.CHROMA_PATH)
    return client.get_or_create_collection(
        name="helix_docs",
        metadata={"hnsw:space": "cosine"},
    )


def search_docs(query: str, k: int = 3) -> list[SearchResult]:
    """
    Search the vector store for the top-k most relevant document chunks.

    Args:
        query: The search query string.
        k: Number of top results to return.

    Returns:
        List of SearchResult objects with chunk_id, content, score, and metadata.
        Scores are cosine similarity in [0, 1] (higher = more relevant).
    """
    collection = _get_collection()

    # Check if collection has documents
    if collection.count() == 0:
        logger.warning("ChromaDB collection is empty. Run ingest first.")
        return []

    results = collection.query(
        query_texts=[query],
        n_results=min(k, collection.count()),
        include=["documents", "metadatas", "distances"],
    )

    search_results: list[SearchResult] = []

    if not results["ids"] or not results["ids"][0]:
        return search_results

    ids = results["ids"][0]
    documents = results["documents"][0] if results["documents"] else [""] * len(ids)
    distances = results["distances"][0] if results["distances"] else [0.0] * len(ids)
    metadatas = results["metadatas"][0] if results["metadatas"] else [{}] * len(ids)

    for chunk_id, doc, distance, meta in zip(ids, documents, distances, metadatas):
        # ChromaDB cosine distance is in [0, 2]; convert to similarity [0, 1]
        similarity = max(0.0, min(1.0, 1.0 - distance))
        search_results.append(
            SearchResult(
                chunk_id=chunk_id,
                content=doc,
                score=round(similarity, 4),
                metadata=meta if meta else {},
            )
        )

    return search_results
