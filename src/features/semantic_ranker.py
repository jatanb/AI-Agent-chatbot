"""
src/features/semantic_ranker.py

#1 — Semantic Search with Embeddings
Uses sentence-transformers to embed query and job descriptions,
then ranks results by cosine similarity.
"""
from __future__ import annotations
import numpy as np
from typing import Optional


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity between two vectors."""
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-9))


def get_embedder():
    """Lazy load — only imports when first called to avoid slow startup."""
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer("all-MiniLM-L6-v2")


def semantic_rank(query: str, results: list[dict], top_k: int = 6) -> list[dict]:
    """
    Rank job/internship results by semantic similarity to query.

    Args:
        query:   user search query
        results: list of result dicts with 'title' and 'description'
        top_k:   how many top results to return

    Returns:
        results sorted by semantic relevance, with 'sem_score' added
    """
    if not results:
        return results

    try:
        model = get_embedder()

        # Embed query
        query_emb = model.encode(query, normalize_embeddings=True)

        # Embed each result — combine title + description for richer signal
        scored = []
        for r in results:
            text = f"{r.get('title', '')} {r.get('description', '')} {r.get('eligibility', '')}"
            result_emb = model.encode(text, normalize_embeddings=True)
            score = cosine_similarity(query_emb, result_emb)
            scored.append({**r, "sem_score": round(score, 4)})

        # Sort by score descending
        scored.sort(key=lambda x: x["sem_score"], reverse=True)
        return scored[:top_k]

    except ImportError:
        # sentence-transformers not installed — return as-is
        return results[:top_k]
    except Exception:
        return results[:top_k]


def batch_embed(texts: list[str]) -> np.ndarray:
    """Embed multiple texts at once — faster than one by one."""
    model = get_embedder()
    return model.encode(texts, normalize_embeddings=True, batch_size=32)