"""
RAG – retrieval-augmented generation pipeline.

Startup:
  1. Load support_articles.json
  2. Build (or load) FAISS index
  3. Expose retrieve() for query-time use
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any

import numpy as np
import faiss

from src.config import (
    ARTICLES_FILE,
    TOP_K_ARTICLES,
    FAISS_INDEX_FILE,
)
from src.embeddings import embed_query, build_and_save_index, load_index

logger = logging.getLogger(__name__)

# ── Module-level singletons ───────────────────────────────────────────────────
_index: faiss.Index | None = None
_metadata: list[dict] | None = None          # [{article_id, title, category}, …]
_articles_map: dict[str, dict] | None = None  # article_id → full article dict


# ── Initialisation ────────────────────────────────────────────────────────────

def init_rag() -> None:
    """
    Load articles and ensure FAISS index is ready.
    Called once at application startup.
    """
    global _index, _metadata, _articles_map

    # Load raw articles
    if not os.path.exists(ARTICLES_FILE):
        raise FileNotFoundError(f"Support articles not found at {ARTICLES_FILE}")

    with open(ARTICLES_FILE, "r", encoding="utf-8") as f:
        articles: list[dict[str, Any]] = json.load(f)

    _articles_map = {a["article_id"]: a for a in articles}

    # Try loading pre-built index first
    _index, _metadata = load_index()

    if _index is None or _index.ntotal != len(articles):
        logger.info("No valid FAISS index found – building from scratch …")
        _index, _metadata = build_and_save_index(articles)

    logger.info("RAG initialised with %d articles.", len(articles))


# ── Query-time retrieval ──────────────────────────────────────────────────────

def retrieve(query: str, top_k: int = TOP_K_ARTICLES) -> list[dict[str, Any]]:
    """
    Embed *query* and return the top-k matching articles with scores.

    Returns list of:
    {
        "article_id": str,
        "title": str,
        "category": str,
        "issue": str,
        "resolution": str,
        "escalation_condition": str,
        "similarity_score": float   # cosine similarity [0, 1]
    }
    """
    if _index is None or _metadata is None:
        raise RuntimeError("RAG system not initialised. Call init_rag() first.")

    query_vec = embed_query(query).reshape(1, -1)

    k = min(top_k, _index.ntotal)
    scores, indices = _index.search(query_vec, k)

    results: list[dict[str, Any]] = []
    for score, idx in zip(scores[0], indices[0]):
        if idx == -1:          # FAISS sentinel for "no result"
            continue
        meta = _metadata[idx]
        art_id = meta["article_id"]
        full_article = _articles_map.get(art_id, {})
        results.append({
            **full_article,
            "similarity_score": float(round(score, 4)),
        })

    return results


def get_all_articles() -> list[dict[str, Any]]:
    """Return all articles (used by the /articles endpoint)."""
    if _articles_map is None:
        return []
    return list(_articles_map.values())
