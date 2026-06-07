"""
app.py — Scheme Scout with login + deadline alerts
Run: streamlit run app.py
"""
import streamlit as st
import time
from agent import run_agent
from src.database.database import (
    create_session, get_user_sessions, update_session_title,
    delete_session, save_message, get_messages,
    save_scheme, get_saved_schemes, delete_saved_scheme, create_alert
)
from src.auth.auth import login, register, logout_user, is_logged_in, current_user
from src.resume.resume import extract_text_from_pdf, parse_resume_with_gemini, build_search_query

st.set_page_config(page_title="Scheme Scout", page_icon="🔍", layout="wide")

st.html("""
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600&display=swap" rel="stylesheet">
<style>
*, *::before, *::after { font-family: 'Inter', sans-serif !important; }
html, body, .stApp { background: #0d0d0d !important; color: #ccc !important; }
#MainMenu, footer, header { visibility: hidden !important; }
[data-testid="collapsedControl"],[aria-label="Close sidebar"],[aria-label="Collapse sidebar"] { display: none !important; }

/* Sidebar */
section[data-testid="stSidebar"] { background: #0f0f0f !important; border-right: 1px solid #1a1a1a !important; }
section[data-testid="stSidebar"] > div { background: #0f0f0f !important; padding: 1.25rem 1rem !important; }
section[data-testid="stSidebar"] * { font-family: 'Inter', sans-serif !important; }
section[data-testid="stSidebar"] .stButton > button {
    background: #181818 !important;
    border: 1px solid #222 !important;
    color: #777 !important;
    text-align: left !important;
    padding: 8px 12px !important;
    border-radius: 8px !important;
    width: 100% !important;
    font-size: 13px !important;
    font-weight: 400 !important;
    box-shadow: none !important;
    transition: all 0.15s !important;
}
section[data-testid="stSidebar"] .stButton > button:hover {
    background: #222 !important;
    border-color: #333 !important;
    color: #ddd !important;
}

/* Main content */
.main .block-container { max-width: 680px !important; padding: 2rem 1.5rem 8rem !important; margin: 0 auto !important; }

/* Auth inputs */
.stTextInput input { background: #161616 !important; border: 1px solid #2a2a2a !important; color: #ddd !important; border-radius: 8px !important; font-size: 14px !important; }
.stTextInput input:focus { border-color: #444 !important; box-shadow: none !important; }

/* Chat input — remove black strip */
[data-testid="stChatInput"] { background: transparent !important; }
[data-testid="stChatInput"] > div { background: transparent !important; }
[data-testid="stChatInput"] textarea {
    background: #161616 !important; border: 1px solid #2a2a2a !important;
    color: #ddd !important; font-size: 14px !important; border-radius: 12px !important;
}
[data-testid="stBottom"] { background: #0d0d0d !important; }
[data-testid="stBottom"] > div { background: #0d0d0d !important; border-top: none !important; padding: 0.5rem 0 1rem !important; }

/* Buttons */
.stButton > button { background: transparent !important; border: 1px solid #222 !important; color: #555 !important; font-size: 13px !important; border-radius: 8px !important; font-family: 'Inter', sans-serif !important; box-shadow: none !important; }
.stButton > button:hover { border-color: #444 !important; color: #ccc !important; background: #1a1a1a !important; }
[data-testid="stChatMessage"] { background: transparent !important; border: none !important; padding: 0 !important; }
[data-testid="chatAvatarIcon-user"] { display: none !important; }
hr { border-color: #1a1a1a !important; }
::-webkit-scrollbar { width: 3px; }
::-webkit-scrollbar-thumb { background: #222; border-radius: 2px; }
</style>
""")

# ── Init state ────────────────────────────────────────────────────────────
for k, v in {"current_session": None, "editing": None,
              "edit_text": "", "active_tab": "chat",
              "auth_mode": "login", "resume_profile": None,
              "resume_name": ""}.items():
    if k not in st.session_state:
        st.session_state[k] = v


# ════════════════════════════════════════════════════════════════════════
# AUTH PAGE
# ════════════════════════════════════════════════════════════════════════
if not is_logged_in():

    # Center container
    _, col, _ = st.columns([1, 2, 1])
    with col:
        st.markdown("""
        <div style="text-align:center;padding:3rem 0 2rem;">
            <div style="font-size:26px;font-weight:600;color:#eee;letter-spacing:-0.03em;">
                Recents
            </div>
            <div style="font-size:13px;color:#444;margin-top:6px;font-weight:400;">
                Find Indian opportunities
            </div>
        </div>""", unsafe_allow_html=True)

        # Toggle buttons
        c1, c2 = st.columns(2)
        with c1:
            if st.button("Login", use_container_width=True, key="mode_login"):
                st.session_state.auth_mode = "login"
                st.rerun()
        with c2:
            if st.button("Register", use_container_width=True, key="mode_reg"):
                st.session_state.auth_mode = "register"
                st.rerun()

        st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

        # ── LOGIN FORM ──
        if st.session_state.auth_mode == "login":
            with st.form("login_form", clear_on_submit=False):
                email    = st.text_input("Email", placeholder="you@email.com")
                password = st.text_input("Password", type="password", placeholder="••••••••")
                submitted = st.form_submit_button("Login", use_container_width=True)
                if submitted:
                    ok, msg = login(email, password)
                    if ok:
                        st.rerun()
                    else:
                        st.error(msg)

        # ── REGISTER FORM ──
        else:
            with st.form("register_form", clear_on_submit=False):
                name   = st.text_input("Full name", placeholder="Your name")
                email  = st.text_input("Email", placeholder="you@email.com")
                passwd = st.text_input("Password", type="password", placeholder="Min 6 characters")
                submitted = st.form_submit_button("Create account", use_container_width=True)
                if submitted:
                    ok, msg = register(name, email, passwd)
                    if ok:
                        st.rerun()
                    else:
                        st.error(msg)

    # Hard stop — nothing below renders
    st.stop()


# ════════════════════════════════════════════════════════════════════════
# LOGGED IN — get user, ensure session
# ════════════════════════════════════════════════════════════════════════
user = current_user()
if not user:
    st.session_state.clear()
    st.rerun()

def ensure_session():
    if not st.session_state.current_session:
        sessions = get_user_sessions(user["id"])
        st.session_state.current_session = (
            sessions[0]["id"] if sessions
            else create_session(user["id"])["id"]
        )

ensure_session()

def build_history(messages):
    return [
        {"role": m["role"],
         "text": m["content"] if isinstance(m["content"], str)
                 else m["content"].get("summary", "")}
        for m in messages
    ]

def is_search_query(q):
    kw = ["scholarship","internship","scheme","fellowship","grant","yojana",
          "stipend","eligibility","deadline","govt","government","ministry",
          "fund","education","student","award","programme","csir","ugc",
          "drdo","isro","aicte","nsp","pm internship","find","list","apply"]
    return any(k in q.lower() for k in kw)

def get_steps(query):
    q = query.lower()
    if any(w in q for w in ["scholarship","merit","sc","st","obc","minority","nsp"]):
        return [("🔍","Searching scholarship databases"),
                ("🏛️","Checking NSP and ministry portals"),
                ("📋","Reading eligibility and deadlines")]
    elif any(w in q for w in ["internship","intern","training"]):
        return [("🔍","Searching internship programmes"),
                ("🏢","Checking PM Internship, DRDO, ISRO portals"),
                ("📋","Extracting stipend and deadline details")]
    elif any(w in q for w in ["fellowship","research","phd","csir","ugc","dst"]):
        return [("🔍","Searching research fellowships"),
                ("🔬","Checking CSIR, UGC, DST databases"),
                ("📋","Compiling fellowship details")]
    else:
        return [("🔍","Searching government portals"),
                ("📡","Fetching latest information"),
                ("📋","Generating answer")]

def card_html(r):
    title    = r.get("title","Untitled")
    rtype    = r.get("type","Scheme")
    desc     = r.get("description","")
    deadline = r.get("deadline","")
    amount   = r.get("amount","")
    elig     = r.get("eligibility","")
    ministry = r.get("ministry","")
    link     = r.get("link","")
    meta = ""
    if deadline: meta += f'<span style="margin-right:14px"><b style="color:#aaa;font-weight:500">Deadline</b>&nbsp;{deadline}</span>'
    if amount:   meta += f'<span style="margin-right:14px"><b style="color:#aaa;font-weight:500">Amount</b>&nbsp;{amount}</span>'
    if elig:     meta += f'<span style="margin-right:14px"><b style="color:#aaa;font-weight:500">Eligibility</b>&nbsp;{elig}</span>'
    if ministry: meta += f'<span><b style="color:#aaa;font-weight:500">By</b>&nbsp;{ministry}</span>'
    link_html = f'<a href="{link}" target="_blank" style="color:#4a9eff;font-size:12px;text-decoration:none;display:inline-block;margin-top:8px;">Official Portal →</a>' if link else ""
    return f"""
    <div style="background:#161616;border:1px solid #222;border-radius:10px;
                padding:14px 16px;margin:6px 0;">
        <div style="font-size:14px;font-weight:500;color:#ddd;margin-bottom:6px;">
            {title}
            <span style="font-size:11px;font-weight:400;color:#555;background:#1e1e1e;
                         border:1px solid #2a2a2a;border-radius:4px;padding:2px 7px;
                         margin-left:8px;">{rtype}</span>
        </div>
        <div style="font-size:13px;color:#777;font-weight:400;line-height:1.6;margin-bottom:8px;">{desc}</div>
        <div style="font-size:12px;color:#555;font-weight:400;line-height:1.8;">{meta}</div>
        {link_html}
    </div>"""

def steps_html(done, active=None):
    html = '<div style="padding:4px 0;">'
    for icon, text in done:
        html += f'<div style="display:flex;align-items:center;gap:8px;padding:2px 0;font-size:13px;color:#444;"><span style="color:#22c55e;font-size:11px;">✓</span><span>{text}</span></div>'
    if active:
        icon, text = active
        html += f'<div style="display:flex;align-items:center;gap:8px;padding:2px 0;font-size:13px;color:#888;"><span>{icon}</span><span>{text}…</span></div>'
    html += "</div>"
    return html


# ── SIDEBAR ───────────────────────────────────────────────────────────────
with st.sidebar:
    # Logo + user
    st.markdown(f"""
    <div style="padding:0.5rem 0.25rem 1rem;">
        <div style="font-size:16px;font-weight:600;color:#e0e0e0;
                    letter-spacing:-0.02em;">🔍 Scheme Scout</div>
        <div style="font-size:12px;color:#3a3a3a;margin-top:3px;">
            {user['name']}
        </div>
    </div>""", unsafe_allow_html=True)

    # New chat button
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
        st.markdown('<div style="font-size:12px;color:#2a2a2a;padding:4px 10px;">No chats yet</div>',
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
                ensure_session()
                st.rerun()

    # Spacer + bottom items
    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
    st.markdown('<div style="font-size:11px;color:#2a2a2a;padding:4px 10px 8px;">Gemini · LangGraph · Tavily</div>',
                unsafe_allow_html=True)
    if st.button("Logout", use_container_width=True, key="logout"):
        logout_user()
        st.rerun()


# ── SAVED SCHEMES PAGE ────────────────────────────────────────────────────
if st.session_state.active_tab == "saved":
    st.markdown('<div style="font-size:22px;font-weight:600;color:#eee;margin-bottom:16px;">Saved Schemes</div>',
                unsafe_allow_html=True)
    saved = get_saved_schemes(user["id"])
    if not saved:
        st.markdown('<div style="color:#444;font-size:14px;font-weight:400;padding:2rem 0;">No saved schemes yet.</div>',
                    unsafe_allow_html=True)
    else:
        for s in saved:
            col_card, col_del = st.columns([9, 1])
            with col_card:
                st.markdown(card_html(s), unsafe_allow_html=True)
                if s.get("deadline"):
                    with st.expander("Set deadline alert"):
                        alert_email = st.text_input("Email", value=user["email"], key=f"ae_{s['id']}")
                        alert_days  = st.selectbox("Alert me", ["7 days before","3 days before","1 day before","On deadline day"], key=f"ad_{s['id']}")
                        if st.button("Set alert", key=f"ab_{s['id']}"):
                            from datetime import datetime, timedelta
                            days_map = {"7 days before":7,"3 days before":3,"1 day before":1,"On deadline day":0}
                            try:
                                dl = datetime.strptime(s["deadline"], "%B %d, %Y")
                                al = dl - timedelta(days=days_map[alert_days])
                                create_alert(user["id"], s["id"], alert_email, al.strftime("%Y-%m-%d"))
                                st.success(f"Alert set for {al.strftime('%b %d, %Y')}")
                            except Exception:
                                st.info("Alert saved.")
            with col_del:
                if st.button("🗑", key=f"ds_{s['id']}"):
                    delete_saved_scheme(s["id"])
                    st.rerun()
    st.stop()



# ── RESUME PAGE ─────────────────────────────────────────────
if st.session_state.active_tab == "resume":
    import time as _time
    st.markdown(
        "<div style='font-size:22px;font-weight:600;color:#eee;margin-bottom:6px;'>"
        "Resume-Based Search</div>",
        unsafe_allow_html=True)
    st.markdown(
        "<div style='font-size:13px;color:#555;margin-bottom:20px;'>"
        "Upload your resume — AI will find best matching opportunities for you.</div>",
        unsafe_allow_html=True)


    uploaded = st.file_uploader("Upload resume (PDF only)", type=["pdf"], key="resume_upload")

    if uploaded:
        with st.spinner("Reading your resume..."):
            text = extract_text_from_pdf(uploaded)

        if text.startswith("Error"):
            st.error(text)
        else:
            with st.spinner("Analysing profile with Gemini..."):
                profile = parse_resume_with_gemini(text)
                st.session_state.resume_profile = profile
                st.session_state.resume_name = uploaded.name

            # Show extracted profile
            edu = profile.get("education", {})
            st.markdown(
                "<div style='background:#161616;border:1px solid #222;border-radius:10px;"
                "padding:16px;margin:12px 0;'>",
                unsafe_allow_html=True)
            st.markdown(
                "<div style='font-size:13px;font-weight:500;color:#aaa;margin-bottom:10px;'>"
                "Profile extracted from resume</div>",
                unsafe_allow_html=True)
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
            st.markdown("</div>", unsafe_allow_html=True)

            looking_for = st.selectbox(
                "What are you looking for?",
                ["internship","scholarship","job","fellowship","government scheme"],
                key="resume_looking")
            profile["looking_for"] = looking_for

            if st.button("Find matching opportunities", type="primary", key="resume_search"):
                query = build_search_query(profile)
                step_ph = st.empty()
                steps = [("👤","Reading your profile"),
                         ("🔍","Searching matched opportunities"),
                         ("📋","Ranking results by relevance")]
                step_ph.markdown(steps_html([], steps[0]), unsafe_allow_html=True)
                _time.sleep(0.3)
                step_ph.markdown(steps_html([steps[0]], steps[1]), unsafe_allow_html=True)
                try:
                    result = run_agent(query=query, category=None, chat_history=[])
                except Exception as e:
                    result = {"summary": f"Error: {e}", "results": [], "sources": [], "type": "search"}
                n = len(result.get("results", []))
                step_ph.markdown(
                    steps_html([steps[0], steps[1]], (steps[2][0], f"Found {n} matches")),
                    unsafe_allow_html=True)
                _time.sleep(0.3)
                step_ph.empty()

                sess = create_session(user["id"], title=f"Resume: {uploaded.name[:20]}")
                st.session_state.current_session = sess["id"]
                save_message(sess["id"], "user",
                             f"Find {looking_for} opportunities for: {edu.get('degree','')} {edu.get('field','')} with skills in {', '.join(profile.get('skills',[])[:4])}")
                save_message(sess["id"], "assistant", result)
                st.session_state.active_tab = "chat"
                st.rerun()



    st.stop()

# ── CHAT PAGE ─────────────────────────────────────────────────────────────
messages = get_messages(st.session_state.current_session)

if not messages:
    st.markdown("""
    <div style="padding:3rem 0 1rem;">
        <div style="font-size:26px;font-weight:600;color:#eee;letter-spacing:-0.03em;margin-bottom:8px;">
            Recents
        </div>
        <div style="font-size:15px;font-weight:400;color:#555;line-height:1.7;">
            Find Jobs, internships instantly.
        </div>
    </div>""", unsafe_allow_html=True)

else:
    for msg in messages:
        if msg["role"] == "user":
            mid = msg.get("id","")
            if st.session_state.editing == mid:
                new_text = st.text_area("", value=st.session_state.edit_text,
                                        key=f"ea_{mid}", label_visibility="collapsed")
                ca, cb, _ = st.columns([1,1,6])
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
                st.markdown(f"""
                <div style="background:#1c1c1c;border:1px solid #2a2a2a;border-radius:14px;
                            padding:12px 16px;margin:10px 0 4px;color:#e0e0e0;
                            font-size:15px;font-weight:400;line-height:1.7;
                            font-family:Inter,sans-serif;">{msg['content']}</div>""",
                            unsafe_allow_html=True)
        else:
            result = msg["content"]
            with st.chat_message("assistant", avatar="🔍"):
                st.markdown(f"""
                <div style="color:#c8c8c8;font-size:15px;font-weight:400;
                            line-height:1.85;padding:4px 0 10px;
                            font-family:Inter,sans-serif;">{result.get("summary","")}</div>""",
                            unsafe_allow_html=True)
                results = result.get("results", [])
                if results:
                    st.markdown(f'<div style="font-size:12px;color:#444;margin-bottom:6px;">{len(results)} opportunities found</div>',
                                unsafe_allow_html=True)
                    for r in results:
                        st.markdown(card_html(r), unsafe_allow_html=True)
                sources = result.get("sources", [])
                if sources:
                    srcs = "  ·  ".join(f'<a href="{s}" style="color:#333;font-size:11px;">{s[:45]}</a>' for s in sources[:3])
                    st.markdown(f'<div style="margin-top:6px;color:#333;font-size:11px;">Sources: {srcs}</div>',
                                unsafe_allow_html=True)


# ── Chat input ────────────────────────────────────────────────────────────
if prompt := st.chat_input("Ask about any Jobs internship…"):
    prompt = prompt.strip()
    save_message(st.session_state.current_session, "user", prompt)
    if len(messages) == 0:
        update_session_title(st.session_state.current_session, prompt[:32])

    st.markdown(f"""
    <div style="background:#1c1c1c;border:1px solid #2a2a2a;border-radius:14px;
                padding:12px 16px;margin:10px 0 4px;color:#e0e0e0;
                font-size:15px;font-weight:400;line-height:1.7;
                font-family:Inter,sans-serif;">{prompt}</div>""",
                unsafe_allow_html=True)

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
            s1, s2, s3 = steps
            step_ph.markdown(steps_html([], s1), unsafe_allow_html=True)
            time.sleep(0.35)
            step_ph.markdown(steps_html([s1], s2), unsafe_allow_html=True)
            try:
                result = run_agent(query=prompt, category=None,
                                   chat_history=build_history(messages))
            except Exception as e:
                result = {"summary": f"Error: {e}", "results": [], "sources": [], "type": "chat"}
            n = len(result.get("results", []))
            s3 = (s3[0], f"Found {n} results, generating answer")
            step_ph.markdown(steps_html([s1, s2], s3), unsafe_allow_html=True)
            time.sleep(0.3)
            step_ph.empty()

    save_message(st.session_state.current_session, "assistant", result)
    st.rerun()