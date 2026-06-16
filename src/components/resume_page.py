"""
src/components/resume_page.py
Resume analysis page — skill match, missing skills, suggestions.
"""
import streamlit as st
from agent import run_agent
from src.database.database import create_session, save_message
from src.resume.resume import (
    extract_text_from_pdf,
    parse_resume_with_groq,
    build_search_query,
    calculate_match,
    generate_suggestions,
)


def friendly_error(e):
    err = str(e).lower()
    if "api key" in err or "401" in err:
        return "API key issue. Please check your GROQ_API_KEY in .env"
    if "429" in err or "quota" in err:
        return "Too many requests. Please wait a moment and try again."
    return f"Error: {str(e)}"


def render_resume_page(user):
    st.subheader("📄 Resume Analyzer")
    st.caption("Upload your resume — AI extracts your skills, finds matching jobs, shows match % and missing skills.")

    # ── Upload ────────────────────────────────────────────────────────────
    if not st.session_state.get("resume_profile"):
        uploaded = st.file_uploader("", type=["pdf"],
                                    key="resume_upload",
                                    label_visibility="collapsed")
        if uploaded:
            with st.spinner("Reading your resume…"):
                text = extract_text_from_pdf(uploaded)

            if text.startswith("Error"):
                st.error("Could not read PDF. Make sure it is a valid PDF file.")
                st.stop()

            with st.spinner("Analysing with Groq AI…"):
                try:
                    profile = parse_resume_with_groq(text)
                    st.session_state.resume_profile  = profile
                    st.session_state.resume_name     = uploaded.name
                    st.session_state.resume_jobs     = []
                    st.session_state.resume_suggestions = []
                    st.rerun()
                except Exception as e:
                    st.error(friendly_error(e))
        st.stop()

    # ── Profile loaded ────────────────────────────────────────────────────
    profile = st.session_state.resume_profile
    edu     = profile.get("education", {})

    col_top, col_btn = st.columns([6, 2])
    with col_top:
        st.success(f"Resume loaded: **{st.session_state.resume_name}**")
    with col_btn:
        if st.button("↑ Upload new", key="resume_new"):
            for k in ["resume_profile","resume_name","resume_jobs","resume_suggestions"]:
                st.session_state.pop(k, None)
            st.rerun()

    st.divider()

    # ── Profile summary ───────────────────────────────────────────────────
    st.markdown("### 👤 Your Profile")
    c1, c2, c3 = st.columns(3)
    with c1:
        if edu.get("degree"):
            st.write(f"**Degree:** {edu['degree']}")
        if edu.get("field"):
            st.write(f"**Field:** {edu['field']}")
        if edu.get("college"):
            st.write(f"**College:** {edu['college']}")
        if edu.get("year"):
            st.write(f"**Year:** {edu['year']}")
        if edu.get("cgpa"):
            st.write(f"**CGPA:** {edu['cgpa']}")
    with c2:
        if profile.get("technical_skills"):
            st.write("**Technical Skills:**")
            st.write(", ".join(profile["technical_skills"][:10]))
        if profile.get("tools"):
            st.write("**Tools:**")
            st.write(", ".join(profile["tools"][:8]))
    with c3:
        if profile.get("frameworks"):
            st.write("**Frameworks:**")
            st.write(", ".join(profile["frameworks"][:8]))
        if profile.get("domains"):
            st.write("**Domains:**")
            st.write(", ".join(profile["domains"][:5]))
        if profile.get("certifications"):
            st.write("**Certifications:**")
            st.write(", ".join(profile["certifications"][:4]))

    if profile.get("projects"):
        with st.expander(f"📁 Projects ({len(profile['projects'])})"):
            for p in profile["projects"]:
                st.markdown(f"**{p.get('name','')}** — {p.get('description','')}")
                if p.get("tech_used"):
                    st.caption(f"Tech: {', '.join(p['tech_used'])}")

    if profile.get("summary"):
        st.info(profile["summary"])

    st.divider()

    # ── Job search ────────────────────────────────────────────────────────
    st.markdown("### 🔍 Find Matching Jobs")

    looking_for = st.selectbox(
        "What are you looking for?",
        ["internship", "job", "remote job", "fresher job"],
        key="resume_looking"
    )
    profile["looking_for"] = looking_for

    if st.button("Search matching jobs", type="primary", key="resume_search"):
        query = build_search_query(profile)
        with st.status("Searching...", expanded=True) as status:
            st.write("🔍 Building personalized search query…")
            st.write(f"🎯 Query: `{query[:80]}...`")
            try:
                result = run_agent(
                    query=query, category=None, chat_history=[],
                    thread_id=st.session_state.get("current_session", "resume")
                )
                jobs = result.get("results", [])
                st.session_state.resume_jobs = jobs

                # Generate suggestions
                st.write("💡 Generating improvement suggestions…")
                suggestions = generate_suggestions(profile, jobs)
                st.session_state.resume_suggestions = suggestions

                status.update(
                    label=f"Found {len(jobs)} matching jobs",
                    state="complete", expanded=False
                )
            except Exception as e:
                st.error(friendly_error(e))
                status.update(label="Search failed", state="error")
                st.stop()

        # Save to chat history
        sess = create_session(user["id"],
                              title=f"Resume: {st.session_state.resume_name[:20]}")
        st.session_state.current_session = sess["id"]
        save_message(sess["id"], "user",
                     f"Find {looking_for}: {edu.get('degree','')} {edu.get('field','')} "
                     f"skills: {', '.join(profile.get('technical_skills',[])[:4])}")
        save_message(sess["id"], "assistant", result)

    # ── Job results with match % ───────────────────────────────────────────
    jobs = st.session_state.get("resume_jobs", [])
    if jobs:
        st.divider()
        st.markdown(f"### 💼 {len(jobs)} Jobs Found — Skill Match Analysis")

        for i, job in enumerate(jobs):
            match = calculate_match(profile, job)
            pct   = match["match_pct"]

            # Color based on match %
            if pct >= 70:
                color = "🟢"
            elif pct >= 40:
                color = "🟡"
            else:
                color = "🔴"

            with st.container(border=True):
                col1, col2, col3 = st.columns([5, 1, 1])
                with col1:
                    st.markdown(f"**{job.get('title', 'Untitled')}**")
                    st.caption(f"🏢 {job.get('ministry', 'Company')}  •  {job.get('type', 'Job')}")
                with col2:
                    st.metric("Match", f"{color} {pct}%")
                with col3:
                    if job.get("amount"):
                        st.metric("Salary", job["amount"][:12])

                if job.get("description"):
                    st.write(job["description"])

                # Matched vs missing skills
                if match["matched"]:
                    st.success(f"✅ You have: {', '.join(list(match['matched'])[:6])}")
                if match["missing"]:
                    st.warning(f"❌ Missing: {', '.join(list(match['missing'])[:6])}")

                if job.get("link"):
                    st.markdown(f"[Apply Now →]({job['link']})")

        st.divider()

        # ── Improvement suggestions ───────────────────────────────────────
        suggestions = st.session_state.get("resume_suggestions", [])
        if suggestions:
            st.markdown("### 💡 How to Improve Your Resume")
            st.caption("Based on analysis of all job matches above")
            for i, s in enumerate(suggestions, 1):
                st.write(f"**{i}.** {s}")

    st.stop()