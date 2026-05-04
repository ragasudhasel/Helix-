"""
CLI ingest script: reads .md files, chunks them, generates embeddings,
and upserts to ChromaDB with deterministic chunk IDs.

Usage:
    python -m app.rag.ingest --path docs/

Chunking strategy (justified in README):
    Fixed-size token chunking at 500 tokens with 50-token overlap.
    This balances retrieval precision (chunks are small enough to be
    topically focused) with context continuity (overlap prevents
    losing information at chunk boundaries). Token-based rather than
    character-based to match LLM context window semantics.
"""

import argparse
import hashlib
import logging
import sys
from pathlib import Path

import chromadb
import frontmatter
import tiktoken

from app.config import settings

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

CHUNK_SIZE = 500       # tokens
CHUNK_OVERLAP = 50     # tokens


def _get_tokenizer() -> tiktoken.Encoding:
    """Use cl100k_base tokenizer (same family as Gemini approximate token counting)."""
    return tiktoken.get_encoding("cl100k_base")


def _make_chunk_id(filename: str, chunk_index: int) -> str:
    """Deterministic chunk ID = md5(filename + chunk_index). Idempotent on re-ingest."""
    raw = f"{filename}:{chunk_index}"
    return hashlib.md5(raw.encode()).hexdigest()[:12]


def _chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Split text into token-based chunks with overlap."""
    enc = _get_tokenizer()
    tokens = enc.encode(text)

    if len(tokens) <= chunk_size:
        return [text]

    chunks: list[str] = []
    start = 0
    while start < len(tokens):
        end = min(start + chunk_size, len(tokens))
        chunk_tokens = tokens[start:end]
        chunk_text = enc.decode(chunk_tokens)
        chunks.append(chunk_text)
        if end >= len(tokens):
            break
        start += chunk_size - overlap

    return chunks


def _extract_metadata(post: frontmatter.Post) -> dict[str, str]:
    """Extract frontmatter metadata fields."""
    meta: dict[str, str] = {}
    if "title" in post.metadata:
        meta["title"] = str(post.metadata["title"])
    if "product_area" in post.metadata:
        meta["product_area"] = str(post.metadata["product_area"])
    return meta


def ingest_directory(docs_path: str) -> int:
    """
    Read all .md files from docs_path, chunk them, and upsert to ChromaDB.
    Returns the total number of chunks upserted.
    """
    path = Path(docs_path)
    if not path.exists():
        logger.error(f"Directory does not exist: {docs_path}")
        sys.exit(1)

    md_files = list(path.glob("*.md"))
    if not md_files:
        logger.warning(f"No .md files found in {docs_path}")
        return 0

    # Initialize ChromaDB persistent client
    client = chromadb.PersistentClient(path=settings.CHROMA_PATH)
    collection = client.get_or_create_collection(
        name="helix_docs",
        metadata={"hnsw:space": "cosine"},
    )

    total_chunks = 0

    for md_file in sorted(md_files):
        logger.info(f"Processing: {md_file.name}")
        post = frontmatter.load(str(md_file))
        content = post.content
        base_meta = _extract_metadata(post)

        chunks = _chunk_text(content)
        logger.info(f"  → {len(chunks)} chunk(s)")

        chunk_ids: list[str] = []
        chunk_docs: list[str] = []
        chunk_metas: list[dict[str, str]] = []

        for i, chunk in enumerate(chunks):
            chunk_id = _make_chunk_id(md_file.name, i)
            meta = {
                **base_meta,
                "source_file": md_file.name,
                "chunk_index": str(i),
            }
            chunk_ids.append(chunk_id)
            chunk_docs.append(chunk)
            chunk_metas.append(meta)

        # Upsert (idempotent — same IDs overwrite, no duplicates)
        collection.upsert(
            ids=chunk_ids,
            documents=chunk_docs,
            metadatas=chunk_metas,
        )
        total_chunks += len(chunks)

    logger.info(f"Ingested {total_chunks} chunks from {len(md_files)} files.")
    return total_chunks


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ingest .md documents into ChromaDB for RAG"
    )
    parser.add_argument(
        "--path",
        type=str,
        required=True,
        help="Path to directory containing .md files",
    )
    args = parser.parse_args()
    ingest_directory(args.path)


if __name__ == "__main__":
    main()
