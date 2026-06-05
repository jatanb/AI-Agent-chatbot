"""
agent.py
Flow: query → intent_classifier → chat_reply OR web_search → synthesize
"""
import os
import json
from typing import TypedDict, Optional

from dotenv import load_dotenv
from langgraph.graph import StateGraph, END
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage
from tavily import TavilyClient
from langchain_groq import ChatGroq

load_dotenv()


class AgentState(TypedDict):
    query: str
    category: Optional[str]
    chat_history: list
    intent: str
    web_results: list
    context: str
    answer: dict
    error: Optional[str]


def get_llm():
    return ChatGroq(
        model="llama-3.3-70b-versatile",
        groq_api_key=os.environ["GROQ_API_KEY"],
        temperature=0.2,
    )

def extract_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(
            part.get("text", "") if isinstance(part, dict) else str(part)
            for part in content
        )
    return str(content)


# ── Node 1: Classify intent ───────────────────────────────────────────────
def intent_classifier(state: AgentState) -> AgentState:
    llm = get_llm()
    system = """You are an intent classifier for  a government opportunity search tool.

Classify the user message as exactly one of:
- "chat"   → greetings, thanks, casual talk, questions about the app
- "search" → anything about scholarships, internships, schemes, fellowships, grants, government programs

Reply with ONLY one word: chat  OR  search"""

    resp = llm.invoke([
        SystemMessage(content=system),
        HumanMessage(content=f"User message: {state['query']}")
    ])
    intent = extract_text(resp.content).strip().lower()
    intent = "search" if "search" in intent else "chat"
    return {**state, "intent": intent}


# ── Node 2a: Chat reply (no search) ──────────────────────────────────────
def chat_reply(state: AgentState) -> AgentState:
    llm = get_llm()
    msgs = [SystemMessage(content="""You are a friendly AI assistant that helps Indian students find government scholarships, internships, and schemes.
For casual messages, reply naturally in 1-3 sentences. Remind users they can search for government opportunities.""")]

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


# ── Node 2b: Web search ───────────────────────────────────────────────────
def web_search(state: AgentState) -> AgentState:
    try:
        client = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])
        cat = state.get("category") or ""
        q = f"India government {cat} {state['query']} 2025 scholarship internship scheme"
        res = client.search(query=q, max_results=7, search_depth="advanced", include_answer=True)
        return {**state, "web_results": res.get("results", [])}
    except Exception as e:
        return {**state, "web_results": [], "error": str(e)}


# ── Node 3: Build context ─────────────────────────────────────────────────
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


# ── Node 4: Synthesize answer ─────────────────────────────────────────────
def synthesize(state: AgentState) -> AgentState:
    llm = get_llm()
    system = """You are — an AI assistant helping Indian students find government opportunities.

Extract all relevant scholarships, internships, and schemes from the search results.

Return ONLY valid JSON. No markdown. No code fences.

{
  "summary": "2-3 sentence overview",
  "results": [
    {
      "title": "scheme name",
      "type": "Scholarship | Internship | Scheme | Fellowship | Grant",
      "description": "what it is",
      "deadline": "date or Ongoing or null",
      "amount": "amount or null",
      "eligibility": "who can apply",
      "ministry": "issuing body",
      "link": "URL or null"
    }
  ],
  "sources": ["url1", "url2"]
}

Only use facts from context. Never hallucinate."""

    raw = ""
    try:
        resp = llm.invoke([
            SystemMessage(content=system),
            HumanMessage(content=f"Query: {state['query']}\n\nContext:\n{state['context']}\n\nReturn JSON only.")
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


# ── Router ────────────────────────────────────────────────────────────────
def route_intent(state: AgentState) -> str:
    return state.get("intent", "search")


# ── Build graph ───────────────────────────────────────────────────────────
def build_agent():
    g = StateGraph(AgentState)
    g.add_node("classifier", intent_classifier)
    g.add_node("chat_reply", chat_reply)
    g.add_node("web_search", web_search)
    g.add_node("build_context", build_context)
    g.add_node("synthesize", synthesize)
    g.set_entry_point("classifier")
    g.add_conditional_edges("classifier", route_intent, {
        "chat": "chat_reply",
        "search": "web_search",
    })
    g.add_edge("chat_reply", END)
    g.add_edge("web_search", "build_context")
    g.add_edge("build_context", "synthesize")
    g.add_edge("synthesize", END)
    return g.compile()

agent = build_agent()


def run_agent(query: str, category: str = None, chat_history: list = None) -> dict:
    result = agent.invoke({
        "query": query,
        "category": category,
        "chat_history": chat_history or [],
        "intent": "",
        "web_results": [],
        "context": "",
        "answer": {},
        "error": None,
    })
    return result["answer"]