"""
src/features/planner.py
Multi-step query planner feature.

Detects complex personal queries and breaks them into
multiple targeted sub-searches run in parallel via Tavily.

Used by agent.py as two extra nodes:
  query_planner → parallel_search
"""
import os
import json
from datetime import datetime
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_groq import ChatGroq


def get_llm():
    return ChatGoogleGenerativeAI(model="gemini-3.5-flash", temperature=0.2)


def extract_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(
            part.get("text", "") if isinstance(part, dict) else str(part)
            for part in content
        )
    return str(content)


# ── Detection ─────────────────────────────────────────────────────────────

def is_complex_query(query: str) -> bool:
    """
    Returns True if query describes a personal profile
    and needs multi-step planning.

    Examples that trigger:
      "I am SC student Gujarat final year B.Tech CS"
      "I'm a girl from MP studying BSc, suggest scholarships"
      "OBC student Maharashtra MBA second year what can I apply"
    """
    signals = [
        "i am", "i'm", "my background", "for me", "suggest me",
        "what can i", "based on my", "i have", "i belong",
        "i study", "i am a", "i'm a", "as a student",
        "sc student", "st student", "obc student", "minority student",
        "girl student", "female student", "disabled student",
        "final year", "first year", "second year", "third year",
        "b.tech", "m.tech", "mba", "bsc", "msc", "phd student",
        "from gujarat", "from maharashtra", "from rajasthan",
        "from kerala", "from up", "from bihar", "from mp",
        "from karnataka", "from tamil", "from bengal",
    ]
    q = query.lower()
    # Needs at least 2 signals to be considered complex
    return sum(1 for s in signals if s in q) >= 2


# ── Node: Query planner ───────────────────────────────────────────────────

def query_planner(state: dict) -> dict:
    """
    LangGraph node.
    Breaks one complex query into 3-4 targeted sub-search strings.
    Adds sub_queries to state.
    """
    llm = get_llm()

    today = datetime.now().strftime("%B %Y")
    system = f"""You are a search query planner for a job and internship finder.

Given a personal profile query, break it into 3-4 specific search queries 
that together find ALL relevant jobs and internships across platforms.

Return ONLY a valid JSON array of strings. No markdown. No explanation.

Example output:
["Python developer internship Naukri {today}",
 "fresher software engineer job LinkedIn {today}",
 "B.Tech CS internship Internshala {today}",
 "entry level developer job Indeed India {today}"]

Rules:
- Each query targets a different platform (LinkedIn, Naukri, Internshala, Indeed, Glassdoor)
- Include the person's skills and field
- Always include {today} for freshness
- Maximum 4 queries"""

    try:
        resp = llm.invoke([
            SystemMessage(content=system),
            HumanMessage(content=f"User query: {state['query']}\n\nGenerate 3-4 targeted search queries.")
        ])
        raw = extract_text(resp.content).strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        sub_queries = json.loads(raw)
        if not isinstance(sub_queries, list):
            raise ValueError("Not a list")
        sub_queries = [str(q) for q in sub_queries[:4]]
    except Exception:
        # Fallback — build basic sub-queries from original query
        sub_queries = [
            f"{state['query']} scholarship 2025 India",
            f"{state['query']} internship 2025",
            f"{state['query']} government scheme 2025",
        ]

    return {**state, "sub_queries": sub_queries}


# ── Node: Parallel search ─────────────────────────────────────────────────

def parallel_search(state: dict) -> dict:
    """
    LangGraph node.
    Runs each sub_query through Tavily and merges + deduplicates results.
    """
    from tavily import TavilyClient
    client = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])

    all_results = []
    seen_urls = set()

    today = datetime.now().strftime("%B %Y")
    for sub_q in state.get("sub_queries", []):
        try:
            res = client.search(
                query=f"{sub_q} {today} site:linkedin.com OR site:naukri.com OR site:internshala.com OR site:indeed.com OR site:glassdoor.com",
                max_results=5,
                search_depth="advanced",
                include_answer=False,
            )
            for r in res.get("results", []):
                url = r.get("url", "")
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    r["matched_query"] = sub_q
                    all_results.append(r)
        except Exception:
            continue

    return {**state, "web_results": all_results}