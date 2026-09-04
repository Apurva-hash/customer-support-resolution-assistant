"""
embeddings.py – local embedding service (no API key required).

Uses sentence-transformers (all-MiniLM-L6-v2) for 384-dim dense vectors
and handles FAISS index persistence.  Drop-in replacement for the
original google-generativeai based embeddings.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any

import numpy as np
import faiss
from sentence_transformers import SentenceTransformer

from src.config import (
    FAISS_INDEX_FILE,
    FAISS_META_FILE,
    FAISS_INDEX_DIR,
)

logger = logging.getLogger(__name__)

# ── Model singleton ────────────────────────────────────────────────────────────
_ST_MODEL_NAME = "all-MiniLM-L6-v2"   # 80 MB, 384-dim, fast CPU inference
_model: SentenceTransformer | None = None


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        logger.info("Loading sentence-transformer model '%s' …", _ST_MODEL_NAME)
        _model = SentenceTransformer(_ST_MODEL_NAME)
        logger.info("Model loaded.")
    return _model


# ── Public helpers ─────────────────────────────────────────────────────────────

def _normalise(vec: np.ndarray) -> np.ndarray:
    """L2-normalise so cosine ≈ inner-product (FAISS IndexFlatIP)."""
    norm = np.linalg.norm(vec)
    return vec / norm if norm > 0 else vec


def embed_text(text: str) -> np.ndarray:
    """Return a normalised float32 embedding vector for *text*."""
    model = _get_model()
    vec = model.encode(text, normalize_embeddings=True).astype(np.float32)
    return vec


def embed_query(text: str) -> np.ndarray:
    """Return a normalised float32 query vector (same as embed_text here)."""
    return embed_text(text)


# ── Index build / save / load ──────────────────────────────────────────────────

def build_and_save_index(articles: list[dict[str, Any]]) -> tuple[faiss.Index, list[dict]]:
    """
    Embed every article and persist a FAISS flat inner-product index.
    Returns (index, metadata_list).
    """
    os.makedirs(FAISS_INDEX_DIR, exist_ok=True)

    # Determine dim from a test embedding
    sample_vec = embed_text("test")
    dim = sample_vec.shape[0]

    index = faiss.IndexFlatIP(dim)

    vectors: list[np.ndarray] = []
    metadata: list[dict] = []

    logger.info("Building FAISS index for %d articles …", len(articles))
    for art in articles:
        text = (
            f"{art['title']}. "
            f"Issue: {art['issue']}. "
            f"Resolution: {art['resolution']}. "
            f"Category: {art['category']}."
        )
        vec = embed_text(text)
        vectors.append(vec)
        metadata.append({
            "article_id": art["article_id"],
            "title": art["title"],
            "category": art["category"],
        })

    matrix = np.stack(vectors)
    index.add(matrix)

    faiss.write_index(index, FAISS_INDEX_FILE)
    with open(FAISS_META_FILE, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    logger.info("FAISS index saved → %s  (%d vectors)", FAISS_INDEX_FILE, index.ntotal)
    return index, metadata


def load_index() -> tuple[faiss.Index, list[dict]] | tuple[None, None]:
    """Load persisted FAISS index + metadata. Returns (None, None) on failure."""
    if not os.path.exists(FAISS_INDEX_FILE) or not os.path.exists(FAISS_META_FILE):
        return None, None
    try:
        index = faiss.read_index(FAISS_INDEX_FILE)
        with open(FAISS_META_FILE, "r", encoding="utf-8") as f:
            metadata = json.load(f)
        logger.info("FAISS index loaded ← %s  (%d vectors)", FAISS_INDEX_FILE, index.ntotal)
        return index, metadata
    except Exception as exc:
        logger.error("Failed to load FAISS index: %s", exc)
        return None, None
