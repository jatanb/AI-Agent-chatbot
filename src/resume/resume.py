"""
src/resume/resume.py

Resume analyzer using Groq:
1. Extract all skills, education, experience from PDF
2. Find matching jobs/internships via Tavily
3. Calculate skill match % per job
4. Detect missing skills
5. Suggest resume improvements
"""
from __future__ import annotations

import io
import os
import json
from dotenv import load_dotenv
from groq import Groq

load_dotenv()
groq_client = Groq(api_key=os.environ.get("GROQ_API_KEY", ""))


# ── 1. Extract text from PDF ──────────────────────────────────────────────

def extract_text_from_pdf(uploaded_file) -> str:
    try:
        from PyPDF2 import PdfReader
        reader = PdfReader(io.BytesIO(uploaded_file.read()))
        text = ""
        for page in reader.pages:
            text += page.extract_text() or ""
        return text.strip()
    except Exception as e:
        return f"Error reading PDF: {e}"


# ── 2. Parse resume with Groq ─────────────────────────────────────────────

def parse_resume_with_groq(resume_text: str) -> dict:
    """
    Extract complete structured profile from resume text.
    Uses Groq Llama — fast and accurate.
    """
    prompt = f"""You are an expert resume parser. Extract ALL important information from this resume.

Return ONLY valid JSON, no markdown, no code fences:
{{
  "name": "candidate full name",
  "email": "email or null",
  "phone": "phone or null",
  "location": "city, state or null",
  "education": {{
    "degree": "B.Tech / M.Tech / BCA / MCA / MBA / BSc / etc",
    "field": "Computer Science / Electronics / Data Science / etc",
    "college": "college name",
    "year": "current year / final year / graduate / 1st year / etc",
    "cgpa": "cgpa or percentage if mentioned"
  }},
  "total_experience_years": 0,
  "technical_skills": ["Python", "Machine Learning", "React"],
  "soft_skills": ["Communication", "Problem Solving"],
  "tools": ["Git", "Docker", "VS Code"],
  "frameworks": ["LangChain", "FastAPI", "TensorFlow"],
  "domains": ["AI/ML", "Web Development", "Data Science"],
  "projects": [
    {{
      "name": "project name",
      "description": "brief description",
      "tech_used": ["tech1", "tech2"]
    }}
  ],
  "experience": [
    {{
      "role": "job title",
      "company": "company name",
      "duration": "duration",
      "description": "what they did"
    }}
  ],
  "certifications": ["cert1", "cert2"],
  "languages": ["English", "Hindi"],
  "looking_for": "internship / job / both",
  "summary": "2-3 sentence professional summary based on resume"
}}

Resume:
{resume_text[:4000]}"""

    try:
        resp = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
        )
        raw = resp.choices[0].message.content.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        return json.loads(raw)
    except Exception as e:
        return {
            "name": "", "email": None, "phone": None,
            "education": {}, "technical_skills": [],
            "soft_skills": [], "tools": [], "frameworks": [],
            "domains": [], "projects": [], "experience": [],
            "certifications": [], "looking_for": "internship",
            "summary": "", "error": str(e)
        }


# ── 3. Build search query from profile ───────────────────────────────────

def build_search_query(profile: dict) -> str:
    from datetime import datetime
    today = datetime.now().strftime("%B %Y")

    edu     = profile.get("education", {})
    skills  = profile.get("technical_skills", [])[:4]
    domains = profile.get("domains", [])[:2]
    looking = profile.get("looking_for", "internship")
    degree  = edu.get("degree", "")
    field   = edu.get("field", "")
    year    = edu.get("year", "")

    parts = [looking]
    if skills:
        parts.extend(skills[:3])
    if field:
        parts.append(field)
    if year and "final" in str(year).lower():
        parts.append("fresher")
    parts.append(f"India {today}")
    parts.append("LinkedIn Naukri Internshala")

    return " ".join(parts)


# ── 4. Calculate skill match % for a job ────────────────────────────────

def calculate_match(profile: dict, job: dict) -> dict:
    """
    Calculate how well a candidate matches a specific job.
    Returns match %, matched skills, missing skills.
    """
    # All candidate skills combined
    candidate_skills = set(
        s.lower() for s in
        profile.get("technical_skills", []) +
        profile.get("soft_skills", []) +
        profile.get("tools", []) +
        profile.get("frameworks", [])
    )

    # Extract job requirements from description + eligibility
    job_text = f"{job.get('title','')} {job.get('description','')} {job.get('eligibility','')}".lower()

    # Common tech skills to check for
    common_skills = [
        "python","java","javascript","typescript","react","node","django","flask",
        "fastapi","sql","mysql","mongodb","postgresql","machine learning","deep learning",
        "tensorflow","pytorch","scikit-learn","pandas","numpy","docker","kubernetes",
        "git","aws","gcp","azure","html","css","tailwind","c++","data analysis",
        "nlp","computer vision","langchain","api","rest","graphql","excel","tableau",
        "power bi","communication","teamwork","problem solving","leadership","agile"
    ]

    # Find skills mentioned in job
    job_required = {s for s in common_skills if s in job_text}

    if not job_required:
        # Fallback — use job title words as requirements
        title_words = set(job.get("title", "").lower().split())
        job_required = title_words & set(common_skills)

    if not job_required:
        return {"match_pct": 75, "matched": [], "missing": [], "total_required": 0}

    matched  = candidate_skills & job_required
    missing  = job_required - candidate_skills
    match_pct = int((len(matched) / max(len(job_required), 1)) * 100)

    return {
        "match_pct":      match_pct,
        "matched":        sorted(matched),
        "missing":        sorted(missing),
        "total_required": len(job_required),
    }


# ── 5. Generate improvement suggestions ──────────────────────────────────

def generate_suggestions(profile: dict, jobs: list[dict]) -> list[str]:
    """
    Analyze profile vs job market and suggest improvements.
    Uses Groq to generate personalized suggestions.
    """
    # Collect all missing skills across top jobs
    all_missing = {}
    for job in jobs[:5]:
        match = calculate_match(profile, job)
        for skill in match.get("missing", []):
            all_missing[skill] = all_missing.get(skill, 0) + 1

    # Most demanded missing skills
    top_missing = sorted(all_missing.items(), key=lambda x: x[1], reverse=True)[:8]
    missing_skills_str = ", ".join(s for s, _ in top_missing) if top_missing else "None identified"

    prompt = f"""You are a career coach. Based on this candidate's profile and the jobs they're targeting,
give 5-7 specific, actionable suggestions to improve their chances.

Candidate profile:
- Degree: {profile.get('education', {}).get('degree', '')} in {profile.get('education', {}).get('field', '')}
- Technical skills: {', '.join(profile.get('technical_skills', [])[:8])}
- Projects: {len(profile.get('projects', []))} projects
- Experience: {profile.get('total_experience_years', 0)} years
- Looking for: {profile.get('looking_for', 'internship')}

Most demanded skills they're missing: {missing_skills_str}

Return ONLY a JSON array of strings, no markdown:
["suggestion 1", "suggestion 2", "suggestion 3"]

Each suggestion must be:
- Specific and actionable (not generic)
- Mention exact skills/tools/platforms
- Achievable within 1-3 months"""

    try:
        resp = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )
        raw = resp.choices[0].message.content.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        suggestions = json.loads(raw)
        return suggestions if isinstance(suggestions, list) else []
    except Exception:
        # Fallback static suggestions based on missing skills
        suggestions = []
        for skill, count in top_missing[:5]:
            suggestions.append(f"Learn {skill.title()} — required in {count} of the top job matches")
        return suggestions if suggestions else [
            "Add more quantifiable achievements to your resume",
            "Build 1-2 projects showcasing your top skills",
            "Get certified in your primary domain",
            "Optimize your LinkedIn profile with relevant keywords",
        ]