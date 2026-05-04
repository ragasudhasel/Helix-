"""
Unit test — search_docs returns results with non-empty chunk IDs
and scores in [0, 1].

Requires: documents ingested via `python -m app.rag.ingest --path docs/`
"""

import os
import tempfile

import pytest

from app.rag.ingest import ingest_directory
from app.rag.search import search_docs


@pytest.fixture(scope="module", autouse=True)
def setup_test_docs(tmp_path_factory):
    """Create temporary test documents and ingest them into a test ChromaDB."""
    # Create a temp directory for test docs
    docs_dir = tmp_path_factory.mktemp("test_docs")

    # Create sample markdown files
    doc1 = docs_dir / "deploy-keys.md"
    doc1.write_text(
        """---
title: Deploy Keys
product_area: security
---

# Deploy Keys

Deploy keys allow secure, automated access to your Helix projects.

## Rotating a Deploy Key

To rotate a deploy key without downtime:
1. Go to Project Settings → Deploy Keys.
2. Click Rotate next to the existing key.
3. A new key is generated. The old key remains valid for 24 hours.
4. Update your CI/CD configuration with the new key.

Best practice: Set up key rotation reminders every 90 days.
""",
        encoding="utf-8",
    )

    doc2 = docs_dir / "build-pipelines.md"
    doc2.write_text(
        """---
title: Build Pipelines
product_area: builds
---

# Build Pipelines

Build pipelines automate your CI/CD workflow in Helix.

## Creating a Pipeline

1. Go to Project → Pipelines → New Pipeline.
2. Select your source repository.
3. Choose a pipeline template or start from scratch.
4. Configure build steps.
5. Set triggers (push, PR, schedule).
""",
        encoding="utf-8",
    )

    # Use a temp ChromaDB path for testing
    chroma_path = str(tmp_path_factory.mktemp("test_chroma"))

    # Patch the settings for test
    from app.config import settings
    original_chroma_path = settings.CHROMA_PATH
    settings.CHROMA_PATH = chroma_path

    # Ingest test documents
    ingest_directory(str(docs_dir))

    yield

    # Restore original setting
    settings.CHROMA_PATH = original_chroma_path


def test_search_docs_returns_results_with_chunk_ids():
    """search_docs should return results with non-empty chunk IDs."""
    results = search_docs("rotate deploy key", k=3)

    assert len(results) > 0, "search_docs should return at least one result"

    for result in results:
        assert result.chunk_id, "chunk_id should not be empty"
        assert len(result.chunk_id) > 0, "chunk_id should have length > 0"
        assert result.content, "content should not be empty"


def test_search_docs_scores_in_range():
    """All scores should be in [0, 1]."""
    results = search_docs("rotate deploy key", k=3)

    assert len(results) > 0, "search_docs should return at least one result"

    for result in results:
        assert 0.0 <= result.score <= 1.0, (
            f"Score {result.score} for chunk {result.chunk_id} is not in [0, 1]"
        )


def test_search_docs_returns_metadata():
    """Results should include source metadata."""
    results = search_docs("build pipeline", k=3)

    assert len(results) > 0
    for result in results:
        assert isinstance(result.metadata, dict)
        # Should have source_file at minimum
        assert "source_file" in result.metadata


def test_search_docs_k_parameter():
    """Requesting k results should return at most k results."""
    results_1 = search_docs("deploy key", k=1)
    results_3 = search_docs("deploy key", k=3)

    assert len(results_1) <= 1
    assert len(results_3) <= 3


def test_search_docs_empty_collection():
    """Search on a query with no matches should return empty gracefully."""
    # This tests that the function doesn't crash on unusual queries
    results = search_docs("xyzzy completely unrelated gibberish 12345", k=3)
    # It may still return results (semantic search is fuzzy), but shouldn't crash
    assert isinstance(results, list)
    for r in results:
        assert 0.0 <= r.score <= 1.0
