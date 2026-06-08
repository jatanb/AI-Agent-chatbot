"""
src/resume/resume.py
PDF resume parser + Gemini profile extractor
"""
import os
import json
import io
from dotenv import load_dotenv
import google.generativeai as genai
from langchain_groq import ChatGroq

load_dotenv()
genai.configure(api_key=os.environ["GROQ_API_KEY"])


def extract_text_from_pdf(uploaded_file) -> str:
    """Extract raw text from a Streamlit uploaded PDF file."""
    try:
        from PyPDF2 import PdfReader
        reader = PdfReader(io.BytesIO(uploaded_file.read()))
        text = ""
        for page in reader.pages:
            text += page.extract_text() or ""
        return text.strip()
    except Exception as e:
        return f"Error reading PDF: {e}"


def parse_resume_with_gemini(resume_text: str) -> dict:
    """
    Send resume text to Gemini → extract structured profile.
    Returns dict with skills, education, experience, etc.
    """
    model = genai.GenerativeModel("gemini-3.5-flash")

    prompt = f"""You are a resume parser. Extract key information from this resume.

Return ONLY valid JSON, no markdown, no code fences:
{{
  "name": "candidate name",
  "education": {{
    "degree": "B.Tech / M.Tech / MBA / etc",
    "field": "Computer Science / Electronics / etc",
    "year": "final year / 2nd year / fresher / graduate",
    "college": "college name if mentioned"
  }},
  "skills": ["skill1", "skill2", "skill3"],
  "experience_years": 0,
  "domains": ["domain1", "domain2"],
  "looking_for": "internship / job ",
  "summary": "2 sentence profile summary for search"
}}

Resume text:
{resume_text[:3000]}"""

    try:
        resp = model.generate_content(prompt)
        raw = resp.text.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        return json.loads(raw)
    except Exception as e:
        return {
            "name": "",
            "education": {"degree": "", "field": "", "year": ""},
            "skills": [],
            "domains": [],
            "experience_years": 0,
            "looking_for": "internship",
            "summary": "Resume uploaded successfully",
            "error": str(e)
        }


def build_search_query(profile: dict) -> str:
    """
    Build a targeted Tavily search query from parsed resume profile.
    """
    degree   = profile.get("education", {}).get("degree", "")
    field    = profile.get("education", {}).get("field", "")
    year     = profile.get("education", {}).get("year", "")
    skills   = profile.get("skills", [])[:4]
    domains  = profile.get("domains", [])[:2]
    looking  = profile.get("looking_for", "internship")

    skill_str  = " ".join(skills)
    domain_str = " ".join(domains)

    query = f"India {looking} 2025 {degree} {field} {year} {skill_str} {domain_str} government scholarship scheme"
    return query.strip()