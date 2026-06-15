"""
src/features/ner_extractor.py

#2 — Named Entity Recognition (NER)
Uses spaCy to extract structured entities from user queries.
Builds precise search queries instead of sending raw text to Tavily.

Example:
  Input:  "Python developer job in Bangalore for freshers"
  Output: {skill: Python, role: developer, location: Bangalore, level: fresher}
  Query:  "Python developer fresher job Bangalore 2026 LinkedIn Naukri"

Install: pip install spacy && python -m spacy download en_core_web_sm
"""
from __future__ import annotations
import re


# ── Domain-specific entity lists ─────────────────────────────────────────
# spaCy's general NER misses tech skills — we add our own lookup

TECH_SKILLS = {
    "python", "java", "javascript", "typescript", "react", "node", "nodejs",
    "django", "flask", "fastapi", "sql", "mysql", "postgresql", "mongodb",
    "machine learning", "ml", "deep learning", "dl", "ai", "artificial intelligence",
    "data science", "nlp", "computer vision", "tensorflow", "pytorch", "keras",
    "scikit-learn", "pandas", "numpy", "matplotlib", "docker", "kubernetes",
    "git", "aws", "gcp", "azure", "linux", "c", "c++", "rust", "golang", "go",
    "html", "css", "tailwind", "vue", "angular", "spring", "kotlin", "swift",
    "r", "scala", "spark", "hadoop", "tableau", "power bi", "excel", "vba",
    "langchain", "langgraph", "openai", "gemini", "llm", "rag", "vector db",
    "selenium", "playwright", "devops", "mlops", "ci/cd", "github actions",
}

EXPERIENCE_LEVELS = {
    "fresher", "entry level", "entry-level", "junior", "mid level", "mid-level",
    "senior", "lead", "intern", "internship", "trainee", "0-1 year",
    "1-2 years", "2-3 years", "3+ years", "experienced",
}

JOB_TYPES = {
    "remote", "wfh", "work from home", "hybrid", "on-site", "onsite",
    "full time", "full-time", "part time", "part-time", "contract", "freelance",
}

PLATFORMS = {
    "linkedin", "naukri", "internshala", "indeed", "glassdoor",
    "shine", "foundit", "monster", "angel", "wellfound",
}


def extract_entities(query: str) -> dict:
    """
    Extract structured entities from a job search query.

    Returns dict with keys:
      skills, role, location, level, job_type, platforms, raw_query
    """
    q = query.lower().strip()
    entities = {
        "skills": [],
        "role": "",
        "location": "",
        "level": "",
        "job_type": "",
        "platforms": [],
        "raw_query": query,
    }

    # Extract tech skills
    for skill in TECH_SKILLS:
        if skill in q:
            entities["skills"].append(skill)

    # Extract experience level
    for level in EXPERIENCE_LEVELS:
        if level in q:
            entities["level"] = level
            break

    # Extract job type
    for jtype in JOB_TYPES:
        if jtype in q:
            entities["job_type"] = jtype
            break

    # Extract platforms mentioned
    for platform in PLATFORMS:
        if platform in q:
            entities["platforms"].append(platform)

    # Try spaCy for location and role extraction
    try:
        import spacy
        try:
            nlp = spacy.load("en_core_web_sm")
        except OSError:
            # Model not downloaded — skip spaCy
            return _build_without_spacy(entities, q)

        doc = nlp(query)

        # Extract locations (GPE = geopolitical entity)
        for ent in doc.ents:
            if ent.label_ == "GPE" and not entities["location"]:
                entities["location"] = ent.text

        # Extract role — look for NOUN chunks near job keywords
        job_keywords = {"developer", "engineer", "analyst", "designer", "manager",
                        "intern", "scientist", "architect", "consultant", "specialist"}
        for chunk in doc.noun_chunks:
            chunk_lower = chunk.text.lower()
            if any(kw in chunk_lower for kw in job_keywords):
                if not entities["role"]:
                    entities["role"] = chunk.text

    except ImportError:
        return _build_without_spacy(entities, q)

    return entities


def _build_without_spacy(entities: dict, q: str) -> dict:
    """Fallback role/location extraction without spaCy."""
    job_keywords = ["developer", "engineer", "analyst", "designer", "manager",
                    "intern", "scientist", "architect", "consultant", "specialist"]
    for kw in job_keywords:
        if kw in q:
            # Get the word before the keyword as modifier
            match = re.search(rf"(\w+\s+)?{kw}", q)
            if match:
                entities["role"] = match.group().strip()
                break
    return entities


def build_enhanced_query(entities: dict) -> str:
    """
    Build a precise Tavily search query from extracted entities.

    Example output:
      "Python machine learning developer fresher job Bangalore 2025 LinkedIn Naukri"
    """
    from datetime import datetime
    today = datetime.now().strftime("%B %Y")

    parts = []

    # Skills first — most important for matching
    if entities["skills"]:
        parts.extend(entities["skills"][:3])  # top 3 skills

    # Role
    if entities["role"]:
        parts.append(entities["role"])
    else:
        parts.append("job internship")  # default

    # Level
    if entities["level"]:
        parts.append(entities["level"])

    # Job type
    if entities["job_type"]:
        parts.append(entities["job_type"])

    # Location
    if entities["location"]:
        parts.append(entities["location"])

    # Add date for freshness
    parts.append(today)

    # Add platforms
    if entities["platforms"]:
        parts.extend(entities["platforms"])
    else:
        parts.append("LinkedIn Naukri Internshala")

    return " ".join(parts)


def process_query(raw_query: str) -> tuple[str, dict]:
    """
    Main function called by agent.
    Returns (enhanced_query, entities)
    """
    entities = extract_entities(raw_query)
    enhanced = build_enhanced_query(entities)
    return enhanced, entities