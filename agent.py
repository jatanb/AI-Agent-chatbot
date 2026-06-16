"""
agent.py
Flow:
  query → intent_classifier
            ├── "chat"    → chat_reply → END
            ├── "search"  → web_search → build_context → synthesize → END
            └── "complex" → query_planner → parallel_search → merge_context → synthesize → END

Complex = personal queries like "I am SC student Gujarat B.Tech, what can I apply for?"
"""
import os
import json
import asyncio
from datetime import datetime
from pathlib import Path
from langgraph.checkpoint.sqlite import SqliteSaver
from typing import TypedDict, Optional
from langchain_groq import ChatGroq
from dotenv import load_dotenv
from langgraph.graph import StateGraph, END
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage
from tavily import TavilyClient
from src.features.reranker import rerank
from langchain_core.output_parsers import StrOutputParser

load_dotenv()
os.environ.setdefault("GROQ_API_KEY", os.environ.get("GROQ_API_KEY", ""))


# ── State ─────────────────────────────────────────────────────────────────
class AgentState(TypedDict):
    query: str
    category: Optional[str]
    chat_history: list
    intent: str                  # "chat" | "search" | "complex"
    sub_queries: list            # planner output — list of sub-search strings
    web_results: list            # merged results from all searches
    context: str
    answer: dict
    error: Optional[str]


# ── Helpers ───────────────────────────────────────────────────────────────
def get_llm():
    return ChatGroq(model="llama-3.3-70b-versatile", temperature=0.2)

def extract_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(
            part.get("text", "") if isinstance(part, dict) else str(part)
            for part in content
        )
    return str(content)

# Planner feature imported from src/features/
from src.features.planner import is_complex_query, query_planner, parallel_search


# ════════════════════════════════════════════════════════════════════════
# NODE 1 — Intent classifier
# ════════════════════════════════════════════════════════════════════════
def intent_classifier(state: AgentState) -> AgentState:
    # First check if it's a complex personal query
    if is_complex_query(state["query"]):
        return {**state, "intent": "complex"}

    llm = get_llm()
    system = """Classify the user message as exactly one of:
- "chat"   → greetings, thanks, casual talk, questions about the app
- "search" → anything about scholarships, internships, schemes, fellowships, grants

Reply with ONLY one word: chat OR search"""

    resp = llm.invoke([
        SystemMessage(content=system),
        HumanMessage(content=f"User message: {state['query']}")
    ])
    intent = extract_text(resp.content).strip().lower()
    intent = "search" if "search" in intent else "chat"
    return {**state, "intent": intent}


# ════════════════════════════════════════════════════════════════════════
# NODE 2a — Chat reply
# ════════════════════════════════════════════════════════════════════════
def chat_reply(state: AgentState) -> AgentState:
    llm = get_llm()
    msgs = [SystemMessage(content="""You are a friendly AI that helps 
students find different types of internships, and Jobs.
Reply naturally in 3-4 sentences. Remind users they can ask about opportunities.""")]

    for m in state.get("chat_history", [])[-6:]:
        if m["role"] == "user":
            msgs.append(HumanMessage(content=m["text"]))
        else:
            msgs.append(SystemMessage(content=f"You previously replied: {m['text'][:200]}"))

    msgs.append(HumanMessage(content=state["query"]))
    resp = llm.invoke(msgs)
    return {**state, "answer": {
        "summary": extract_text(resp.content).strip(),
        "results": [], "sources": [], "type": "chat"
    }}


# ════════════════════════════════════════════════════════════════════════
# NODE 2b — Simple web search (single query)
# ════════════════════════════════════════════════════════════════════════
def web_search(state: AgentState) -> AgentState:
    try:
        client = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])
        today = datetime.now().strftime("%B %Y")   # e.g. "June 2025"
        q = (f"{state['query']} jobs internship hiring {today} "
             f"site:linkedin.com OR site:naukri.com OR site:internshala.com "
             f"OR site:indeed.com OR site:foundit.in OR site:shine.com OR site:glassdoor.com")
        res = client.search(query=q, max_results=6, search_depth="basic", include_answer=False)
        return {**state, "web_results": res.get("results", [])}
    except Exception as e:
        return {**state, "web_results": [], "error": str(e)}


# query_planner and parallel_search imported from src/features/planner.py


# ════════════════════════════════════════════════════════════════════════
# NODE 4 — Build context (shared by both flows)
# ════════════════════════════════════════════════════════════════════════
def build_context(state: AgentState) -> AgentState:
    if not state["web_results"]:
        return {**state, "context": "No results found."}
    parts = []
    for r in state["web_results"]:
        parts.append(
            f"Source: {r.get('url', '')}\n"
            f"Title: {r.get('title', '')}\n"
            f"Content: {r.get('content', '')[:500]}"
        )
    return {**state, "context": "\n---\n".join(parts)}


# ════════════════════════════════════════════════════════════════════════
# NODE 5 — Synthesize (shared by both flows)
# Complex flow uses a richer prompt with eligibility context
# ════════════════════════════════════════════════════════════════════════
def synthesize(state: AgentState) -> AgentState:
    llm = get_llm()

    is_complex = state.get("intent") == "complex"

    if is_complex:
        today = datetime.now().strftime("%B %d, %Y")
        system = f"""You are an expert AI job and internship finder in india. Today is {today}.

The user has described their profile. Find ALL relevant jobs and internships 
from LinkedIn, Naukri, Internshala, Indeed, Glassdoor and rank by relevance.

Return ONLY valid JSON. No markdown. No code fences.

{{
  "summary": "Personalized 2-3 sentence summary mentioning platforms found and user fit",
  "results": [
    {{
      "title": "job/internship title",
      "type": "Internship | Job | Fresher Job | Remote Job",
      "description": "role and why it matches this user's profile",
      "deadline": "apply by date or Ongoing or null",
      "amount": "salary or stipend or null",
      "eligibility": "skills or experience required",
      "ministry": "company name",
      "link": "apply URL",
      "relevance": "High | Medium | Low"
    }}
  ],
  "sources": ["url1", "url2"]
}}

Rules:
- Sort by relevance: High first
- only give job which suit the user's role.
- Only include {today[:4]} listings
- main thing , you would give company name,skills required,and salary never give null.
- Only use facts from context. Never hallucinate
- Explain WHY each role matches the user"""
    else:
        today = datetime.now().strftime("%B %d, %Y")
        system = f"""You are  an AI job and internship finder in india. Today is {today}.

Extract all relevant jobs and internships from the search results.
Include results from LinkedIn, Naukri, Internshala, Indeed, Glassdoor, Shine, Foundit.

Return ONLY valid JSON. No markdown. No code fences.

{{
  "summary": "2-3 sentence overview mentioning platforms and recency",
  "results": [
    {{
      "title": "job/internship title",
      "type": "Internship | Job | Fresher Job | Remote Job",
      "description": "role description and company",
      "deadline": "apply by date or Ongoing or null",
      "amount": "salary or stipend or null",
      "eligibility": "skills or experience required",
      "ministry": "company name",
      "link": "apply URL"
    }}
  ],
  "sources": ["url1", "url2"]
}}

Rules:
- Only include results from {today[:4]} or very recent
- Never show outdated listings
- never show null in any of thins catagoty must show 
- Only use facts from context. Never hallucinate."""

    raw = ""
    try:
        resp = llm.invoke([
            SystemMessage(content=system),
            HumanMessage(content=f"User query: {state['query']}\n\nContext:\n{state['context']}\n\nReturn JSON only.")
        ])
        raw = extract_text(resp.content).strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        answer = json.loads(raw)
        answer["type"] = "search"
        return {**state, "answer": answer}
    except json.JSONDecodeError:
        return {**state, "answer": {"summary": raw or "No results.", "results": [], "sources": [], "type": "search"}}
    except Exception as e:
        return {**state, "answer": {"summary": f"Error: {e}", "results": [], "sources": [], "type": "search"}, "error": str(e)}


# ════════════════════════════════════════════════════════════════════════
# Routers
# ════════════════════════════════════════════════════════════════════════
def route_intent(state: AgentState) -> str:
    return state.get("intent", "search")


# ════════════════════════════════════════════════════════════════════════
# Build graph
# ════════════════════════════════════════════════════════════════════════
def build_agent():
    g = StateGraph(AgentState)

    g.add_node("classifier",     intent_classifier)
    g.add_node("chat_reply",     chat_reply)
    g.add_node("web_search",     web_search)
    g.add_node("query_planner",  query_planner)
    g.add_node("parallel_search",parallel_search)
    g.add_node("build_context",  build_context)
    g.add_node("synthesize",     synthesize)
    g.add_node("reranker", rerank)

    g.set_entry_point("classifier")

    # Route: chat → chat_reply, search → web_search, complex → query_planner
    g.add_conditional_edges("classifier", route_intent, {
        "chat":    "chat_reply",
        "search":  "web_search",
        "complex": "query_planner",
    })

    # Simple search flow
    g.add_edge("chat_reply",     END)
    g.add_edge("web_search",     "build_context")

    # Complex flow
    g.add_edge("query_planner",  "parallel_search")
    g.add_edge("parallel_search","build_context")
    g.add_edge("reranker",        "build_context")

    # Both flows merge here
    g.add_edge("build_context",  "synthesize")
    g.add_edge("synthesize",     END)

    # SqliteSaver — agent remembers state per session (thread_id)
    Path("./data").mkdir(exist_ok=True)
    import sqlite3
    conn = sqlite3.connect("./data/checkpoints.db", check_same_thread=False)
    memory = SqliteSaver(conn)
    return g.compile(checkpointer=memory)

agent = build_agent()



def run_agent(query: str, category: str = None,
              chat_history: list = None, thread_id: str = "default") -> dict:
    """
    thread_id = session ID from the app.
    LangGraph SqliteSaver uses this to remember agent state per conversation.
    """
    config = {"configurable": {"thread_id": thread_id}}
    result = agent.invoke({
        "query":        query,
        "category":     category,
        "chat_history": chat_history or [],
        "intent":       "",
        "sub_queries":  [],
        "web_results":  [],
        "context":      "",
        "answer":       {},
        "error":        None,
    }, config=config)
    return result["answer"]