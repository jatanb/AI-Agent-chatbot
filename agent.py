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

load_dotenv()
os.environ.setdefault("GOOGLE_API_KEY", os.environ.get("GEMINI_API_KEY", ""))


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
    return ChatGoogleGenerativeAI(
        model="gemini-3.5-flash",
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
    system = """You are an intent classifier a opportunity search tool.

Classify the user message as exactly one of:
- "chat"   → greetings, thanks, casual talk, questions about the app
- "search" → anything about , internships, job  from any kind of privat companny like google ,meta,microsoft and all big compnies along with that any government job or internship user can ask.user can ask any question you have to just answer it accorsing to question.

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
    msgs = [SystemMessage(content="""You are  a friendly AI assistant that helps students find , internships, and jobs.
For casual messages, reply naturally in 1-3 sentences. Remind users they can search for opportunities.
                          note:
                          1) if user ask any other question then internship or job then you have to kindly answer it in detail
                          2) if user ask for spacific job portal's name then you have to answer it only from that portal.
                          
                          """)]

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
        q = f"{cat} {state['query']}  internship job linkedin naukri indeed glassdor internshala gov.in"
        res = client.search(query=q, max_results=10, search_depth="advanced", include_answer=True)
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
    system = """You are an AI assistant helping students find  opportunities.

Extract all relevant  internships, job opportunities from the search results.
Include results from LinkedIn, Naukri, Internshala,indeed, glassdoor and all other platform and government portals.

note:
1) you must have to give live or ongoing opportunities not 2025 or before 2025.
2) if user ask any kind of question other than job or internship ,you must do not have give info about opportunity. you have to extract info if user ask for.

Return ONLY valid JSON. No markdown. No code fences.

{
  "summary": "3-4 sentence overview",
  "results": [
    {
      "title": "scheme name",
      "type": " Internship | Job",
      "description": "what it is",
      "deadline": "date or Ongoing ",
      "amount": "amount or unpaid",
      "eligibility": "who can apply",
      "ministry": "issuing body",
      "link": "URL"
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