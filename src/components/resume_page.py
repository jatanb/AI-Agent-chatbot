"""
src/components/resume_page.py
Resume-based job search page.
"""
import streamlit as st
from agent import run_agent
from src.database.database import create_session, save_message
from src.resume.resume import extract_text_from_pdf, parse_resume, build_search_query


def friendly_error(e):
    err = str(e).lower()
    if "api key" in err or "401" in err:
        return "API key issue. Please check your Gemini/Tavily keys in .env"
    if "429" in err or "quota" in err:
        return "Too many requests. Please wait a moment and try again."
    if "timeout" in err:
        return "Search timed out. Please try again."
    return f"Error: {str(e)}"


def render_resume_page(user):
    st.subheader("Resume-Based Search")
    st.caption("Upload your resume — AI finds matching jobs and internships.")

    if st.session_state.resume_profile:
        profile = st.session_state.resume_profile
        edu = profile.get("education", {})
        st.success(f"Resume loaded: {st.session_state.resume_name}")

        col1, col2 = st.columns(2)
        with col1:
            if edu.get("degree"):
                st.write(f"**Degree:** {edu.get('degree')} — {edu.get('field','')}")
            if edu.get("year"):
                st.write(f"**Year:** {edu.get('year')}")
        with col2:
            if profile.get("skills"):
                st.write(f"**Skills:** {', '.join(profile['skills'][:5])}")
            if profile.get("domains"):
                st.write(f"**Domains:** {', '.join(profile['domains'][:3])}")

        looking_for = st.selectbox("What are you looking for?",
                                   ["internship","job","remote job","fresher job"],
                                   key="resume_looking")
        profile["looking_for"] = looking_for

        ca, cb = st.columns([2, 2])
        with ca:
            if st.button("Find matching opportunities", type="primary", key="resume_search"):
                query = build_search_query(profile)
                with st.spinner("Searching matched jobs and internships…"):
                    try:
                        result = run_agent(query=query, category=None, chat_history=[],
                                           thread_id=st.session_state.current_session or "resume")
                    except Exception as e:
                        result = {"summary": "", "results": [], "sources": [],
                                  "type": "error", "error": friendly_error(e)}
                sess = create_session(user["id"], title=f"Resume: {st.session_state.resume_name[:20]}")
                st.session_state.current_session = sess["id"]
                save_message(sess["id"], "user",
                    f"Find {looking_for} for: {edu.get('degree','')} {edu.get('field','')} "
                    f"skills: {', '.join(profile.get('skills',[])[:4])}")
                save_message(sess["id"], "assistant", result)
                st.session_state.active_tab = "chat"
                st.rerun()
        with cb:
            if st.button("Upload new resume", key="resume_new"):
                st.session_state.resume_profile = None
                st.session_state.resume_name = ""
                st.rerun()
    else:
        uploaded = st.file_uploader("", type=["pdf"], key="resume_upload",
                                    label_visibility="collapsed")
        if uploaded:
            with st.spinner("Reading your resume…"):
                text = extract_text_from_pdf(uploaded)
            if text.startswith("Error"):
                st.error("Could not read PDF. Make sure it is a valid PDF file.")
            else:
                try:
                    with st.spinner("Analysing profile…"):
                        profile = parse_resume(text)
                        st.session_state.resume_profile = profile
                        st.session_state.resume_name = uploaded.name
                    st.rerun()
                except Exception as e:
                    st.error(friendly_error(e))

    st.stop()