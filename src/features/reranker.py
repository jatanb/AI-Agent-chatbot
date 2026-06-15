"""
src/features/reranker.py

#4 — Cross-Encoder Re-Ranking
Uses sentence-transformers cross-encoder to score each result
against the query and re-rank by actual relevance.

Difference from semantic_ranker.py (#1):
  - semantic_ranker: bi-encoder (embed query + doc separately, cosine sim)
    → fast, good for large sets
  - cross-encoder: processes query+doc TOGETHER
    → slower but much more accurate relevance scoring

Flow in agent:
  Tavily returns 10 raw results
        ↓
  cross-encoder scores each (query, result) pair
        ↓
  sort by score, return top 5
        ↓
  user sees only truly relevant results

Install: pip install sentence-transformers
"""
from __future__ import annotations


# Best cross-encoder for semantic similarity — small, fast, CPU-friendly
CROSS_ENCODER_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"


def get_cross_encoder():
    """Lazy load cross-encoder model."""
    from sentence_transformers import CrossEncoder
    return CrossEncoder(CROSS_ENCODER_MODEL)


def rerank_results(query: str, results: list[dict], top_k: int = 5) -> list[dict]:
    """
    Re-rank results using cross-encoder.

    Args:
        query:   original user query
        results: list of result dicts from Tavily/agent
        top_k:   number of top results to return

    Returns:
        top_k results sorted by cross-encoder relevance score
    """
    if not results:
        return results

    if len(results) <= 1:
        return results

    try:
        model = get_cross_encoder()

        # Build (query, document) pairs for cross-encoder
        pairs = []
        for r in results:
            doc = (
                f"{r.get('title', '')} "
                f"{r.get('description', '')} "
                f"{r.get('eligibility', '')} "
                f"{r.get('ministry', '')}"
            ).strip()
            pairs.append((query, doc))

        # Score all pairs at once
        scores = model.predict(pairs)

        # Attach scores to results
        scored = []
        for r, score in zip(results, scores):
            scored.append({**r, "rerank_score": round(float(score), 4)})

        # Sort descending by score
        scored.sort(key=lambda x: x["rerank_score"], reverse=True)

        return scored[:top_k]

    except ImportError:
        # sentence-transformers not installed — return as-is
        return results[:top_k]
    except Exception:
        return results[:top_k]


# ── LangGraph node version ────────────────────────────────────────────────

def rerank(state: dict) -> dict:
    """
    LangGraph node — re-ranks web_results before context is built.

    Plugs in between web_search/parallel_search and build_context.
    """
    web_results = state.get("web_results", [])
    query = state.get("query", "")

    if not web_results or not query:
        return state

    reranked = rerank_results(query, web_results, top_k=6)
    return {**state, "web_results": reranked}