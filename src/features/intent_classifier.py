"""
src/features/intent_classifier.py

#3 — Zero-Shot Intent Classification
Uses sentence-transformers to classify query intent without any training data.
Replaces keyword-based is_search_query() with semantic understanding.

Zero-shot = no training needed, works out of the box.
Model computes similarity between query and label descriptions.

Install: pip install sentence-transformers
"""
from __future__ import annotations

# Intent labels with descriptions — model matches query to closest label
INTENTS = {
    "job_search": (
        "searching for a job, internship, work opportunity, career, hiring, "
        "vacancy, position, role, employment, fresher opening"
    ),
    "resume_help": (
        "help with resume, CV, portfolio, cover letter, ATS, job application"
    ),
    "salary_query": (
        "asking about salary, pay, compensation, stipend, CTC, package"
    ),
    "company_info": (
        "asking about a company, organization, employer, workplace, culture"
    ),
    "casual_chat": (
        "greeting, hello, hi, thanks, help, what can you do, casual conversation"
    ),
}

# Threshold — below this similarity score → treat as casual_chat
CONFIDENCE_THRESHOLD = 0.25


def classify_intent(query: str) -> tuple[str, float]:
    """
    Classify query into one of the INTENTS using zero-shot similarity.

    Returns:
        (intent_label, confidence_score)

    Example:
        "Python ML internship in Bangalore" → ("job_search", 0.72)
        "Hi how are you"                   → ("casual_chat", 0.81)
        "What is the salary at Google?"    → ("salary_query", 0.68)
    """
    try:
        from sentence_transformers import SentenceTransformer, util
        import torch

        model = SentenceTransformer("all-MiniLM-L6-v2")

        query_emb = model.encode(query, convert_to_tensor=True)

        best_intent = "casual_chat"
        best_score  = 0.0

        for intent, description in INTENTS.items():
            desc_emb = model.encode(description, convert_to_tensor=True)
            score = float(util.cos_sim(query_emb, desc_emb)[0][0])
            if score > best_score:
                best_score  = score
                best_intent = intent

        if best_score < CONFIDENCE_THRESHOLD:
            return "casual_chat", best_score

        return best_intent, best_score

    except ImportError:
        # Fallback to keyword matching if sentence-transformers not installed
        return _keyword_fallback(query)


def _keyword_fallback(query: str) -> tuple[str, float]:
    """Simple keyword fallback when sentence-transformers unavailable."""
    kw = ["job","intern","hiring","fresher","vacancy","career",
          "role","developer","engineer","analyst","apply","salary",
          "stipend","remote","wfh","python","java","ml","ai","data"]
    q = query.lower()
    matches = sum(1 for k in kw if k in q)
    if matches >= 2:
        return "job_search", 0.8
    if matches == 1:
        return "job_search", 0.5
    return "casual_chat", 0.9


def is_job_search(query: str) -> bool:
    """
    Drop-in replacement for is_search_query() in chat.py.
    Uses zero-shot classification instead of keyword matching.
    """
    intent, confidence = classify_intent(query)
    return intent in ("job_search", "salary_query", "company_info")