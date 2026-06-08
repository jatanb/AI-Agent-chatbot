"""
app.py — Scheme Scout
Run: streamlit run app.py
"""
import streamlit as st
import time
from agent import run_agent, is_complex_query
from src.auth.auth import login, register, logout_user, is_logged_in, current_user
from src.database.database import (
    create_session, get_user_sessions, update_session_title,
    delete_session, save_message, get_messages,
    save_scheme, get_saved_schemes, delete_saved_scheme, create_alert
)
from src.resume.resume import extract_text_from_pdf, parse_resume_with_gemini, build_search_query
from src.ui.login_page import login_header, login_form, register_form, auth_toggle
from src.ui.chat_page import (
    user_bubble, answer_html, card_html, steps_html,
    welcome_screen, sidebar_logo, sidebar_footer,
    sources_html, results_count
)

st.set_page_config(
    page_title="Scheme Scout",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.html("""
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600&display=swap" rel="stylesheet">
<style>
*, *::before, *::after { font-family: 'Inter', sans-serif !important; }
html, body, .stApp { background: #0d0d0d !important; color: #ccc !important; }
#MainMenu, footer, header { visibility: hidden !important; }
[data-testid="collapsedControl"],
[data-testid="stSidebarCollapsedControl"],
[aria-label="Close sidebar"],
[aria-label="Collapse sidebar"] { display: none !important; }

section[data-testid="stSidebar"] { background: #0f0f0f !important; border-right: 1px solid #1a1a1a !important; }
section[data-testid="stSidebar"] > div { background: #0f0f0f !important; padding: 1.25rem 1rem !important; }
section[data-testid="stSidebar"] * { font-family: 'Inter', sans-serif !important; }
section[data-testid="stSidebar"] .stButton > button {
    background: #181818 !important; border: 1px solid #222 !important;
    color: #777 !important; text-align: left !important; padding: 8px 12px !important;
    border-radius: 8px !important; width: 100% !important; font-size: 13px !important;
    font-weight: 400 !important; box-shadow: none !important; transition: all 0.15s !important;
}
section[data-testid="stSidebar"] .stButton > button:hover {
    background: #222 !important; border-color: #333 !important; color: #ddd !important;
}
.main .block-container { max-width: 680px !important; padding: 2rem 1.5rem 8rem !important; margin: 0 auto !important; }
.stTextInput input { background: #161616 !important; border: 1px solid #2a2a2a !important; color: #ddd !important; border-radius: 8px !important; font-size: 14px !important; }
.stTextInput input:focus { border-color: #444 !important; box-shadow: none !important; }
[data-testid="stChatInput"] textarea { background: #161616 !important; border: 1px solid #2a2a2a !important; color: #ddd !important; font-size: 14px !important; border-radius: 12px !important; }
[data-testid="stBottom"] { background: #0d0d0d !important; }
[data-testid="stBottom"] > div { background: #0d0d0d !important; border-top: none !important; padding: 0.5rem 0 1rem !important; }
.stButton > button { background: transparent !important; border: 1px solid #222 !important; color: #555 !important; font-size: 13px !important; border-radius: 8px !important; box-shadow: none !important; }
.stButton > button:hover { border-color: #444 !important; color: #ccc !important; background: #1a1a1a !important; }
button[kind="primary"] { background: #fff !important; color: #000 !important; border: none !important; font-weight: 500 !important; }
button[kind="primary"]:hover { background: #e0e0e0 !important; }
[data-testid="stChatMessage"] { background: transparent !important; border: none !important; padding: 0 !important; }
[data-testid="chatAvatarIcon-user"] { display: none !important; }
hr { border-color: #1a1a1a !important; }
::-webkit-scrollbar { width: 3px; }
::-webkit-scrollbar-thumb { background: #222; border-radius: 2px; }
</style>
""")

# ── Session state ─────────────────────────────────────────────────────────
for k, v in {
    "current_session": None,
    "editing": None,
    "edit_text": "",
    "active_tab": "chat",
    "auth_mode": "login",
    "resume_profile": None,
    "resume_name": "",
}.items():
    if k not in st.session_state:
        st.session_state[k] = v


# ── Helpers ───────────────────────────────────────────────────────────────
def ensure_session(user_id):
    if not st.session_state.current_session:
        sessions = get_user_sessions(user_id)
        st.session_state.current_session = (
            sessions[0]["id"] if sessions
            else create_session(user_id)["id"]
        )

def build_history(messages):
    return [
        {"role": m["role"],
         "text": m["content"] if isinstance(m["content"], str)
                 else m["content"].get("summary", "")}
        for m in messages
    ]

def is_search_query(q):
    kw = ["job","jobs","internship","intern","hiring","fresher","opening",
          "vacancy","role","position","work","career","opportunity","placement",
          "apply","linkedin","naukri","internshala","indeed","glassdoor",
          "salary","stipend","remote","wfh","part time","full time",
          "developer","engineer","analyst","designer","manager","executive",
          "python","java","data","ml","ai","marketing","finance","hr"]
    return any(k in q.lower() for k in kw)

def get_steps(query):
    q = query.lower()
    if is_complex_query(query):
        return [("🧠","Analysing your profile"),
                ("📋","Planning targeted searches"),
                ("🔍","Searching LinkedIn, Naukri, Internshala…"),
                ("⚡","Ranking results by relevance")]
    elif any(w in q for w in ["internship","intern","fresher","trainee"]):
        return [("🔍","Searching internships on Internshala, LinkedIn"),
                ("🏢","Checking Naukri, Indeed, Glassdoor"),
                ("📋","Extracting stipend and apply details")]
    elif any(w in q for w in ["remote","wfh","work from home","freelance"]):
        return [("🔍","Searching remote opportunities"),
                ("💻","Checking LinkedIn, Indeed, Glassdoor"),
                ("📋","Extracting remote job details")]
    else:
        return [("🔍","Searching LinkedIn, Naukri, Indeed"),
                ("🏢","Checking Internshala, Glassdoor, Shine"),
                ("📋","Extracting job details")]


# ════════════════════════════════════════════════════════════════════════
# AUTH PAGE
# ════════════════════════════════════════════════════════════════════════
if not is_logged_in():
    _, col, _ = st.columns([1, 2, 1])
    with col:
        # Design from login_page.py
        login_header()

        # Toggle
        mode = auth_toggle(st.session_state.auth_mode)
        if mode:
            st.session_state.auth_mode = mode
            st.rerun()

        st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

        # Login form
        if st.session_state.auth_mode == "login":
            email, password, submitted = login_form()
            if submitted:
                if not email or not password:
                    st.error("Please fill in all fields.")
                else:
                    ok, msg = login(email, password)
                    if ok:
                        st.rerun()
                    else:
                        st.error(msg)

        # Register form
        else:
            name, email, password, submitted = register_form()
            if submitted:
                if not name or not email or not password:
                    st.error("Please fill in all fields.")
                else:
                    ok, msg = register(name, email, password)
                    if ok:
                        st.rerun()
                    else:
                        st.error(msg)

    st.stop()


# ════════════════════════════════════════════════════════════════════════
# LOGGED IN
# ════════════════════════════════════════════════════════════════════════
user = current_user()
if not user:
    st.session_state.clear()
    st.rerun()

ensure_session(user["id"])


# ── SIDEBAR ───────────────────────────────────────────────────────────────
with st.sidebar:
    # Design from chat_page.py
    st.markdown(sidebar_logo(user["name"]), unsafe_allow_html=True)

    if st.button("＋  New chat", use_container_width=True, key="new_chat"):
        sess = create_session(user["id"])
        st.session_state.current_session = sess["id"]
        st.session_state.active_tab = "chat"
        st.rerun()

    if st.button("📄  Resume Search", use_container_width=True, key="nav_resume"):
        st.session_state.active_tab = "resume"
        st.rerun()

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    # Chat history
    sessions = get_user_sessions(user["id"])
    if not sessions:
        st.markdown(
            '<div style="font-size:12px;color:#2a2a2a;padding:4px 10px;">No chats yet</div>',
            unsafe_allow_html=True)
    for sess in sessions:
        active = sess["id"] == st.session_state.current_session
        c1, c2 = st.columns([5, 1])
        with c1:
            label = ("● " if active else "  ") + sess["title"]
            if st.button(label, key=f"s_{sess['id']}", use_container_width=True):
                st.session_state.current_session = sess["id"]
                st.session_state.active_tab = "chat"
                st.rerun()
        with c2:
            if st.button("✕", key=f"d_{sess['id']}"):
                delete_session(sess["id"])
                st.session_state.current_session = None
                ensure_session(user["id"])
                st.rerun()

    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
    st.markdown(sidebar_footer(), unsafe_allow_html=True)

    if st.button("Logout", use_container_width=True, key="logout"):
        logout_user()
        st.rerun()


# ════════════════════════════════════════════════════════════════════════
# RESUME PAGE
# ════════════════════════════════════════════════════════════════════════
if st.session_state.active_tab == "resume":
    st.markdown(
        "<div style='font-size:22px;font-weight:600;color:#eee;margin-bottom:6px;'>"
        "Resume-Based Search</div>", unsafe_allow_html=True)
    st.markdown(
        "<div style='font-size:13px;color:#555;margin-bottom:20px;'>"
        "Upload your resume — AI will find best matching opportunities for you.</div>",
        unsafe_allow_html=True)

    if st.session_state.resume_profile:
        profile = st.session_state.resume_profile
        edu = profile.get("education", {})

        st.success(f"Resume loaded: {st.session_state.resume_name}")

        col1, col2 = st.columns(2)
        with col1:
            if edu.get("degree"):
                st.markdown(f"**Degree:** {edu.get('degree')} — {edu.get('field','')}")
            if edu.get("year"):
                st.markdown(f"**Year:** {edu.get('year')}")
            if profile.get("experience_years") is not None:
                st.markdown(f"**Experience:** {profile.get('experience_years')} yrs")
        with col2:
            if profile.get("skills"):
                st.markdown(f"**Skills:** {', '.join(profile['skills'][:5])}")
            if profile.get("domains"):
                st.markdown(f"**Domains:** {', '.join(profile['domains'][:3])}")

        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

        looking_for = st.selectbox(
            "What are you looking for?",
            ["internship","scholarship","job","fellowship","government scheme"],
            key="resume_looking")
        profile["looking_for"] = looking_for

        ca, cb = st.columns([2, 2])
        with ca:
            if st.button("Find matching opportunities", type="primary", key="resume_search"):
                query = build_search_query(profile)
                step_ph = st.empty()
                steps = [("👤","Reading your profile"),
                         ("🔍","Searching matched opportunities"),
                         ("📋","Ranking by relevance")]
                step_ph.markdown(steps_html([], steps[0]), unsafe_allow_html=True)
                time.sleep(0.3)
                step_ph.markdown(steps_html([steps[0]], steps[1]), unsafe_allow_html=True)
                try:
                    result = run_agent(query=query, category=None, chat_history=[])
                except Exception as e:
                    result = {"summary": f"Error: {e}", "results": [], "sources": [], "type": "search"}
                n = len(result.get("results", []))
                step_ph.markdown(
                    steps_html([steps[0], steps[1]], (steps[2][0], f"Found {n} matches")),
                    unsafe_allow_html=True)
                time.sleep(0.3)
                step_ph.empty()

                sess = create_session(user["id"],
                    title=f"Resume: {st.session_state.resume_name[:20]}")
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
        uploaded = st.file_uploader("Upload resume (PDF only)", type=["pdf"], key="resume_upload")
        if uploaded:
            with st.spinner("Reading your resume…"):
                text = extract_text_from_pdf(uploaded)
            if text.startswith("Error"):
                st.error(text)
            else:
                with st.spinner("Analysing profile..."):
                    profile = parse_resume_with_gemini(text)
                    st.session_state.resume_profile = profile
                    st.session_state.resume_name = uploaded.name
                st.rerun()

    st.stop()


# ════════════════════════════════════════════════════════════════════════
# CHAT PAGE
# ════════════════════════════════════════════════════════════════════════
messages = get_messages(st.session_state.current_session)

if not messages:
    st.markdown(welcome_screen(), unsafe_allow_html=True)

else:
    for msg in messages:

        # User message
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
                        result = run_agent(query=new_text.strip(), category=None,
                                           chat_history=build_history(messages))
                        save_message(st.session_state.current_session, "assistant", result)
                        st.rerun()
                with cb:
                    if st.button("Cancel", key=f"ca_{mid}"):
                        st.session_state.editing = None
                        st.rerun()
            else:
                st.markdown(user_bubble(msg["content"]), unsafe_allow_html=True)

        # Assistant message
        else:
            result = msg["content"]
            with st.chat_message("assistant", avatar="🔍"):
                st.markdown(answer_html(result.get("summary", "")), unsafe_allow_html=True)
                results = result.get("results", [])
                if results:
                    st.markdown(results_count(len(results)), unsafe_allow_html=True)
                    for r in results:
                        st.markdown(card_html(r), unsafe_allow_html=True)
                st.markdown(sources_html(result.get("sources", [])), unsafe_allow_html=True)


# ── Chat input ────────────────────────────────────────────────────────────
if prompt := st.chat_input("Search for jobs, internships, or ask anything…"):
    prompt = prompt.strip()
    save_message(st.session_state.current_session, "user", prompt)
    if len(messages) == 0:
        update_session_title(st.session_state.current_session, prompt[:32])

    st.markdown(user_bubble(prompt), unsafe_allow_html=True)

    with st.chat_message("assistant", avatar="🔍"):
        step_ph = st.empty()

        if not is_search_query(prompt):
            try:
                result = run_agent(query=prompt, category=None,
                                   chat_history=build_history(messages))
            except Exception as e:
                result = {"summary": f"Error: {e}", "results": [], "sources": [], "type": "chat"}
        else:
            steps = get_steps(prompt)
            # Show first 2 steps before running agent
            step_ph.markdown(steps_html([], steps[0]), unsafe_allow_html=True)
            time.sleep(0.3)
            step_ph.markdown(steps_html([steps[0]], steps[1]), unsafe_allow_html=True)
            time.sleep(0.3)
            # Show step 3 if complex (4 steps)
            if len(steps) == 4:
                step_ph.markdown(steps_html([steps[0], steps[1]], steps[2]), unsafe_allow_html=True)
            try:
                result = run_agent(query=prompt, category=None,
                                   chat_history=build_history(messages))
            except Exception as e:
                result = {"summary": f"Error: {e}", "results": [], "sources": [], "type": "chat"}
            n = len(result.get("results", []))
            last = (steps[-1][0], f"Found {n} results, generating answer")
            step_ph.markdown(steps_html(steps[:-1], last), unsafe_allow_html=True)
            time.sleep(0.3)
            step_ph.empty()

    save_message(st.session_state.current_session, "assistant", result)
    st.rerun()