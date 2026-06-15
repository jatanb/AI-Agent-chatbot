"""
src/components/chat.py
Chat page — messages, result cards, search steps, chat input.
"""
import streamlit as st
import time
from agent import run_agent, is_complex_query
from src.database.database import save_message, get_messages, update_session_title
from src.features.intent_classifier import is_job_search
from src.features.ner_extractor import process_query
from src.features.semantic_ranker import semantic_rank


def build_history(messages):
    return [
        {"role": m["role"],
         "text": m["content"] if isinstance(m["content"], str)
                 else m["content"].get("summary", "")}
        for m in messages
    ]

def friendly_error(e):
    err = str(e).lower()
    if "api key" in err or "401" in err:
        return "API key issue. Please check your Gemini/Tavily keys in .env"
    if "429" in err or "quota" in err or "rate limit" in err:
        return "Too many requests. Please wait a moment and try again."
    if "timeout" in err:
        return "Search timed out. Please try again."
    if "network" in err or "connection" in err:
        return "Network issue. Please check your internet connection."
    return f"Error: {str(e)}"

def get_steps(query):
    q = query.lower()
    if is_complex_query(query):
        return [("🧠","Analysing your profile"),
                ("📋","Planning targeted searches"),
                ("🔍","Searching LinkedIn, Naukri, Internshala"),
                ("⚡","Re-ranking results by relevance")]
    elif any(w in q for w in ["internship","intern","fresher","trainee"]):
        return [("🔍","Searching internships on Internshala, LinkedIn"),
                ("🏢","Checking Naukri, Indeed, Glassdoor"),
                ("⚡","Re-ranking by relevance")]
    elif any(w in q for w in ["remote","wfh","work from home"]):
        return [("🔍","Searching remote opportunities"),
                ("💻","Checking LinkedIn, Indeed, Glassdoor"),
                ("⚡","Re-ranking by relevance")]
    else:
        return [("🔍","Searching LinkedIn, Naukri, Indeed"),
                ("🏢","Checking Internshala, Glassdoor, Shine"),
                ("⚡","Re-ranking by relevance")]

@st.cache_data(ttl=3600, show_spinner=False)
def cached_search(prompt: str) -> dict:
    try:
        return run_agent(query=prompt, category=None, chat_history=[], thread_id="cache")
    except Exception as e:
        return {"summary": "", "results": [], "sources": [], "type": "error", "error": friendly_error(e)}

def run_search(prompt, messages):
    steps = get_steps(prompt)
    result = {}

    with st.status("Searching...", expanded=True) as status:
        for icon, label in steps[:-1]:
            st.write(f"{icon} {label}")
            time.sleep(0.3)
        st.write(f"{steps[-1][0]} {steps[-1][1]}…")

        # NER — enhance query before sending to agent
        try:
            enhanced_query, entities = process_query(prompt)
        except Exception:
            enhanced_query = prompt

        try:
            result = run_agent(query=enhanced_query, category=None,
                               chat_history=build_history(messages),
                               thread_id=st.session_state.current_session)
        except Exception as e:
            result = {"summary": "", "results": [], "sources": [],
                      "type": "error", "error": friendly_error(e)}

        # Semantic re-ranking on top of cross-encoder reranker
        if result.get("results"):
            try:
                result["results"] = semantic_rank(enhanced_query, result["results"], top_k=5)
            except Exception:
                pass

        n = len(result.get("results", []))
        status.update(label=f"Found {n} opportunities", state="complete", expanded=False)

    return result

def stream_text(text: str):
    for word in text.split():
        yield word + " "
        time.sleep(0.03)

def render_result(result):
    if result.get("type") == "error":
        st.error(result.get("error", "Something went wrong."))
        return
    if result.get("summary"):
        st.write(result["summary"])
    results = result.get("results", [])
    if results:
        st.caption(f"{len(results)} opportunities found")
        for r in results:
            with st.container(border=True):
                col1, col2 = st.columns([6, 1])
                with col1:
                    st.markdown(f"**{r.get('title','Untitled')}**")
                with col2:
                    st.caption(r.get("type", "Job"))
                if r.get("description"):
                    st.write(r["description"])
                meta_cols = st.columns(4)
                if r.get("deadline"):
                    meta_cols[0].caption(f"Apply by: {r['deadline']}")
                if r.get("amount"):
                    meta_cols[1].caption(f"Salary: {r['amount']}")
                if r.get("eligibility"):
                    meta_cols[2].caption(f"Skills: {r['eligibility']}")
                if r.get("ministry"):
                    meta_cols[3].caption(f"Company: {r['ministry']}")
                # Open in new tab using markdown link
                if r.get("link"):
                    st.markdown(f"[Apply Now →]({r['link']})", unsafe_allow_html=False)


def render_chat_page():

    messages = get_messages(st.session_state.current_session)

    if not messages:
        st.title("Scheme Scout")
        st.write("Find jobs and internships from LinkedIn, Naukri, Internshala, Indeed and more.")
    else:
        for msg in messages:
            if msg["role"] == "user":
                mid = msg.get("id", "")
                if st.session_state.editing == mid:
                    new_text = st.text_area("", value=st.session_state.edit_text,
                                            key=f"ea_{mid}", label_visibility="collapsed")
                    ca, cb, _ = st.columns([1, 1, 6])
                    with ca:
                        if st.button("Send", key=f"se_{mid}", type="primary"):
                            st.session_state.editing = None
                            save_message(st.session_state.current_session, "user", new_text.strip())
                            with st.spinner("Searching…"):
                                try:
                                    result = run_agent(query=new_text.strip(), category=None,
                                                       chat_history=build_history(messages),
                                                       thread_id=st.session_state.current_session)
                                except Exception as e:
                                    result = {"summary":"","results":[],"sources":[],
                                              "type":"error","error":friendly_error(e)}
                            save_message(st.session_state.current_session, "assistant", result)
                            st.rerun()
                    with cb:
                        if st.button("Cancel", key=f"ca_{mid}"):
                            st.session_state.editing = None
                            st.rerun()
                else:
                    with st.chat_message("user"):
                        st.write(msg["content"])
            else:
                with st.chat_message("assistant", avatar="🔍"):
                    result = msg["content"]
                    if result.get("type") == "error":
                        st.error(result.get("error", "Something went wrong."))
                    else:
                        if result.get("summary"):
                            st.write(result["summary"])
                        results = result.get("results", [])
                        if results:
                            st.caption(f"{len(results)} opportunities found")
                            for r in results:
                                with st.container(border=True):
                                    col1, col2 = st.columns([6, 1])
                                    with col1:
                                        st.markdown(f"**{r.get('title','Untitled')}**")
                                    with col2:
                                        st.caption(r.get("type", "Job"))
                                    if r.get("description"):
                                        st.write(r["description"])
                                    meta_cols = st.columns(4)
                                    if r.get("deadline"):
                                        meta_cols[0].caption(f"Apply by: {r['deadline']}")
                                    if r.get("amount"):
                                        meta_cols[1].caption(f"Salary: {r['amount']}")
                                    if r.get("eligibility"):
                                        meta_cols[2].caption(f"Skills: {r['eligibility']}")
                                    if r.get("ministry"):
                                        meta_cols[3].caption(f"Company: {r['ministry']}")
                                    if r.get("link"):
                                        st.markdown(f"[Apply Now →]({r['link']})")


    # Normal chat input
    if prompt := st.chat_input("Search for jobs, internships, or ask anything…"):
        prompt = prompt.strip()
        save_message(st.session_state.current_session, "user", prompt)
        if len(messages) == 0:
            update_session_title(st.session_state.current_session, prompt[:32])

        # Set running flag
        st.session_state.is_running = True
        st.session_state.stop_requested = False

        with st.chat_message("user"):
            st.write(prompt)

        with st.chat_message("assistant", avatar="🔍"):
            if not is_job_search(prompt):
                try:
                    result = run_agent(query=prompt, category=None,
                                       chat_history=build_history(messages),
                                       thread_id=st.session_state.current_session)
                except Exception as e:
                    result = {"summary":"","results":[],"sources":[],
                              "type":"error","error":friendly_error(e)}
            elif is_complex_query(prompt):
                result = run_search(prompt, messages)
            else:
                result = cached_search(prompt)

            # Check if user stopped
            if st.session_state.stop_requested:
                st.session_state.is_running = False
                st.session_state.stop_requested = False
                st.warning("Search stopped.")
                save_message(st.session_state.current_session, "assistant",
                             {"summary": "Search stopped by user.", "results": [], "sources": [], "type": "chat"})
                st.rerun()
                return

            # Stream summary
            if result.get("type") == "error":
                st.error(result.get("error", "Something went wrong."))
            else:
                if result.get("summary"):
                    st.write_stream(stream_text(result["summary"]))
                results = result.get("results", [])
                if results:
                    st.caption(f"{len(results)} opportunities found")
                    for r in results:
                        with st.container(border=True):
                            col1, col2 = st.columns([6, 1])
                            with col1:
                                st.markdown(f"**{r.get('title','Untitled')}**")
                            with col2:
                                st.caption(r.get("type", "Job"))
                            if r.get("description"):
                                st.write(r["description"])
                            meta_cols = st.columns(4)
                            if r.get("deadline"):
                                meta_cols[0].caption(f"Apply by: {r['deadline']}")
                            if r.get("amount"):
                                meta_cols[1].caption(f"Salary: {r['amount']}")
                            if r.get("eligibility"):
                                meta_cols[2].caption(f"Skills: {r['eligibility']}")
                            if r.get("ministry"):
                                meta_cols[3].caption(f"Company: {r['ministry']}")
                            if r.get("link"):
                                st.markdown(f"[Apply Now →]({r['link']})")

        # Done — clear running flag
        st.session_state.is_running = False
        st.session_state.stop_requested = False
        save_message(st.session_state.current_session, "assistant", result)
        st.rerun()