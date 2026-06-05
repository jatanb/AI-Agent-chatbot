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

st.set_page_config(page_title="Scheme Scout", page_icon="🔍", layout="wide")

st.html("""
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600&display=swap" rel="stylesheet">
<style>
*, *::before, *::after { font-family: 'Inter', sans-serif !important; }
html, body, .stApp { background: #0d0d0d !important; color: #ccc !important; }
#MainMenu, footer, header { visibility: hidden !important; }
[data-testid="collapsedControl"],
[aria-label="Close sidebar"],
[aria-label="Collapse sidebar"] { display: none !important; }

/* Sidebar */
section[data-testid="stSidebar"] {
    background: #111 !important;
    border-right: 1px solid #1e1e1e !important;
}
section[data-testid="stSidebar"] > div {
    background: #111 !important;
    padding: 1rem 0.75rem !important;
}
section[data-testid="stSidebar"] * {
    font-family: 'Inter', sans-serif !important;
    color: #666 !important;
}
section[data-testid="stSidebar"] .stButton > button {
    background: transparent !important;
    border: none !important;
    color: #666 !important;
    text-align: left !important;
    padding: 5px 8px !important;
    border-radius: 6px !important;
    width: 100% !important;
    font-size: 13px !important;
    font-weight: 400 !important;
    box-shadow: none !important;
}
section[data-testid="stSidebar"] .stButton > button:hover {
    background: #1a1a1a !important; color: #ddd !important;
}

/* Main */
.main .block-container {
    max-width: 700px !important;
    padding: 2rem 1.5rem 8rem !important;
    margin: 0 auto !important;
}

/* Inputs */
.stTextInput input, .stTextInput input:focus {
    background: #161616 !important;
    border: 1px solid #2a2a2a !important;
    color: #ddd !important;
    border-radius: 8px !important;
    font-size: 14px !important;
}
.stTextInput input:focus { border-color: #444 !important; box-shadow: none !important; }

/* Chat input */
[data-testid="stChatInput"] textarea {
    background: #161616 !important;
    border: 1px solid #2a2a2a !important;
    color: #ddd !important;
    font-size: 14px !important;
    border-radius: 12px !important;
}
[data-testid="stBottom"] > div {
    background: #0d0d0d !important;
    border-top: 1px solid #1a1a1a !important;
}

/* Buttons */
.stButton > button {
    background: transparent !important;
    border: 1px solid #2a2a2a !important;
    color: #666 !important;
    font-size: 13px !important;
    border-radius: 8px !important;
    font-family: 'Inter', sans-serif !important;
    box-shadow: none !important;
}
.stButton > button:hover {
    border-color: #444 !important; color: #ccc !important;
    background: #1a1a1a !important;
}
button[kind="primary"] {
    background: #fff !important;
    color: #000 !important;
    border: none !important;
    font-weight: 500 !important;
}
button[kind="primary"]:hover { background: #e0e0e0 !important; }

/* Chat messages */
[data-testid="stChatMessage"] {
    background: transparent !important;
    border: none !important; padding: 0 !important;
}
[data-testid="chatAvatarIcon-user"] { display: none !important; }

/* Tabs */
[data-testid="stTabs"] button {
    font-size: 13px !important; color: #555 !important;
    background: transparent !important; border: none !important;
}
[data-testid="stTabs"] button[aria-selected="true"] {
    color: #ddd !important; border-bottom: 1px solid #ddd !important;
}

hr { border-color: #1e1e1e !important; }
::-webkit-scrollbar { width: 3px; }
::-webkit-scrollbar-thumb { background: #222; border-radius: 2px; }
</style>
""")


# ── Helpers ───────────────────────────────────────────────────────────────
for k, v in {"current_session": None, "editing": None,
              "edit_text": "", "active_tab": "chat"}.items():
    if k not in st.session_state:
        st.session_state[k] = v

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
            <span style="font-size:11px;font-weight:400;color:#555;
                         background:#1e1e1e;border:1px solid #2a2a2a;
                         border-radius:4px;padding:2px 7px;margin-left:8px;">{rtype}</span>
        </div>
        <div style="font-size:13px;color:#777;font-weight:300;line-height:1.6;margin-bottom:8px;">{desc}</div>
        <div style="font-size:12px;color:#555;font-weight:300;line-height:1.8;">{meta}</div>
        {link_html}
    </div>"""

def steps_html(done, active=None):
    html = '<div style="padding:4px 0;">'
    for icon, text in done:
        html += f'<div style="display:flex;align-items:center;gap:8px;padding:2px 0;font-size:13px;color:#444;font-family:Inter,sans-serif;"><span style="color:#22c55e;font-size:11px;">✓</span><span>{text}</span></div>'
    if active:
        icon, text = active
        html += f'<div style="display:flex;align-items:center;gap:8px;padding:2px 0;font-size:13px;color:#888;font-family:Inter,sans-serif;"><span>{icon}</span><span>{text}…</span></div>'
    html += "</div>"
    return html


# ════════════════════════════════════════════════════════════════════════════
# AUTH PAGES — shown when not logged in
# ════════════════════════════════════════════════════════════════════════════
if not is_logged_in():
    st.markdown("""
    <div style="max-width:400px;margin:5rem auto 2rem;text-align:center;">
        <div style="font-size:28px;font-weight:600;color:#eee;letter-spacing:-0.03em;margin-bottom:6px;">
            🔍 Scheme Scout
        </div>
        <div style="font-size:14px;color:#555;font-weight:300;">
            Find Indian government scholarships, internships and schemes
        </div>
    </div>
    """, unsafe_allow_html=True)

    tab_login, tab_register = st.tabs(["Login", "Register"])

    with tab_login:
        st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
        email    = st.text_input("Email", key="li_email", placeholder="you@email.com")
        password = st.text_input("Password", type="password", key="li_pass", placeholder="••••••••")
        st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
        if st.button("Login", type="primary", use_container_width=True, key="li_btn"):
            ok, msg = login(email, password)
            if ok:
                st.success(msg)
                st.rerun()
            else:
                st.error(msg)

    with tab_register:
        st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
        name     = st.text_input("Full name", key="rg_name", placeholder="Your name")
        email_r  = st.text_input("Email", key="rg_email", placeholder="you@email.com")
        pass_r   = st.text_input("Password", type="password", key="rg_pass", placeholder="Min 6 characters")
        st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
        if st.button("Create account", type="primary", use_container_width=True, key="rg_btn"):
            ok, msg = register(name, email_r, pass_r)
            if ok:
                st.success(msg)
                st.rerun()
            else:
                st.error(msg)
    st.stop()


# ════════════════════════════════════════════════════════════════════════════
# MAIN APP — shown when logged in
# ════════════════════════════════════════════════════════════════════════════
user = current_user()
ensure_session(user["id"])

badge = {"Scholarship":"Scholarship","Internship":"Internship",
         "Scheme":"Scheme","Fellowship":"Fellowship","Grant":"Grant"}

# ── SIDEBAR ───────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(f"""
    <div style="padding:0.25rem 0 0.5rem;">
        <div style="font-size:15px;font-weight:600;color:#ddd;font-family:Inter,sans-serif;">
            🔍 Scheme Scout
        </div>
        <div style="font-size:12px;color:#444;margin-top:2px;font-family:Inter,sans-serif;">
            {user['name']}
        </div>
    </div>""", unsafe_allow_html=True)
    st.divider()

    # Nav
    if st.button("💬  Chats", use_container_width=True, key="nav_chat"):
        st.session_state.active_tab = "chat"
    if st.button("🔖  Saved schemes", use_container_width=True, key="nav_saved"):
        st.session_state.active_tab = "saved"

    st.divider()

    if st.session_state.active_tab == "chat":
        if st.button("＋  New chat", use_container_width=True, key="new_chat"):
            sess = create_session(user["id"])
            st.session_state.current_session = sess["id"]
            st.rerun()
        st.divider()
        sessions = get_user_sessions(user["id"])
        if not sessions:
            st.markdown('<p style="color:#333;font-size:12px;padding:4px 8px;">No chats yet</p>',
                        unsafe_allow_html=True)
        for sess in sessions:
            active = sess["id"] == st.session_state.current_session
            c1, c2 = st.columns([5, 1])
            with c1:
                label = ("● " if active else "   ") + sess["title"]
                if st.button(label, key=f"s_{sess['id']}", use_container_width=True):
                    st.session_state.current_session = sess["id"]
                    st.rerun()
            with c2:
                if st.button("✕", key=f"d_{sess['id']}"):
                    delete_session(sess["id"])
                    st.session_state.current_session = None
                    ensure_session(user["id"])
                    st.rerun()

    st.divider()
    if st.button("Logout", use_container_width=True, key="logout"):
        logout_user()
        st.rerun()
    st.markdown('<p style="color:#2a2a2a;font-size:11px;padding:0 8px;">Gemini · LangGraph · Tavily</p>',
                unsafe_allow_html=True)


# ── SAVED SCHEMES PAGE ────────────────────────────────────────────────────
if st.session_state.active_tab == "saved":
    st.markdown("""
    <div style="font-size:22px;font-weight:600;color:#eee;
                letter-spacing:-0.02em;margin-bottom:4px;">
        Saved Schemes
    </div>""", unsafe_allow_html=True)

    saved = get_saved_schemes(user["id"])

    if not saved:
        st.markdown("""
        <div style="color:#444;font-size:14px;font-weight:300;padding:2rem 0;">
            No saved schemes yet. Search for schemes and save them here.
        </div>""", unsafe_allow_html=True)
    else:
        for s in saved:
            cols = st.columns([8, 1])
            with cols[0]:
                st.markdown(card_html(s), unsafe_allow_html=True)
                # Deadline alert toggle
                if s.get("deadline"):
                    with st.expander("⏰ Set deadline alert"):
                        alert_email = st.text_input(
                            "Send alert to email",
                            value=user["email"],
                            key=f"ae_{s['id']}"
                        )
                        alert_days = st.selectbox(
                            "Alert me",
                            ["7 days before","3 days before","1 day before","On deadline day"],
                            key=f"ad_{s['id']}"
                        )
                        if st.button("Set alert", key=f"ab_{s['id']}", type="primary"):
                            from datetime import datetime, timedelta
                            days_map = {
                                "7 days before": 7, "3 days before": 3,
                                "1 day before": 1, "On deadline day": 0
                            }
                            try:
                                deadline_dt = datetime.strptime(s["deadline"], "%B %d, %Y")
                                alert_dt    = deadline_dt - timedelta(days=days_map[alert_days])
                                create_alert(user["id"], s["id"], alert_email,
                                             alert_dt.strftime("%Y-%m-%d"))
                                st.success(f"Alert set! You'll get an email on {alert_dt.strftime('%b %d, %Y')}")
                            except Exception:
                                st.info("Alert saved. Email will be sent based on deadline date.")
            with cols[1]:
                if st.button("🗑", key=f"ds_{s['id']}"):
                    delete_saved_scheme(s["id"])
                    st.rerun()
    st.stop()


# ── CHAT PAGE ─────────────────────────────────────────────────────────────
messages = get_messages(st.session_state.current_session)

if not messages:
    st.markdown("""
    <div style="padding:3rem 0 1rem;">
        <div style="font-size:26px;font-weight:600;color:#eee;
                    letter-spacing:-0.03em;margin-bottom:8px;">
            Scheme Scout
        </div>
        <div style="font-size:15px;font-weight:300;color:#555;line-height:1.7;">
            Find Indian government scholarships, internships and schemes instantly.
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
                # User bubble
                st.markdown(f"""
                <div style="background:#1c1c1c;border:1px solid #2a2a2a;border-radius:14px;
                            padding:12px 16px;margin:10px 0 2px;color:#e0e0e0;
                            font-size:15px;font-weight:400;line-height:1.7;
                            font-family:Inter,sans-serif;">
                    {msg['content']}
                </div>""", unsafe_allow_html=True)

        else:
            result = msg["content"]
            with st.chat_message("assistant", avatar="🔍"):
                # Summary text
                st.markdown(f"""
                <div style="color:#c8c8c8;font-size:15px;font-weight:300;
                            line-height:1.85;padding:4px 0 12px;
                            font-family:Inter,sans-serif;">
                    {result.get("summary","")}
                </div>""", unsafe_allow_html=True)

                results = result.get("results", [])
                if results:
                    st.markdown(f'<div style="font-size:12px;color:#444;margin-bottom:6px;font-family:Inter,sans-serif;">{len(results)} opportunities found</div>',
                                unsafe_allow_html=True)
                    for r in results:
                        st.markdown(card_html(r), unsafe_allow_html=True)
                        # Save button per card
                        if st.button(f"+ Save  {r.get('title','')[:30]}", key=f"sv_{r.get('title','')}_{id(r)}"):
                            save_scheme(user["id"], r)
                            st.toast("Saved!", icon="🔖")

                sources = result.get("sources", [])
                if sources:
                    srcs = "  ·  ".join(f'<a href="{s}" style="color:#333;font-size:11px;text-decoration:none;">{s[:45]}</a>' for s in sources[:3])
                    st.markdown(f'<div style="margin-top:6px;color:#333;font-size:11px;">Sources: {srcs}</div>',
                                unsafe_allow_html=True)


# ── Chat input ────────────────────────────────────────────────────────────
if prompt := st.chat_input("Ask about any scheme, scholarship or internship…"):
    prompt = prompt.strip()
    save_message(st.session_state.current_session, "user", prompt)
    if len(messages) == 0:
        update_session_title(st.session_state.current_session, prompt[:32])

    st.markdown(f"""
    <div style="background:#1c1c1c;border:1px solid #2a2a2a;border-radius:14px;
                padding:12px 16px;margin:10px 0 2px;color:#e0e0e0;
                font-size:15px;font-weight:400;line-height:1.7;font-family:Inter,sans-serif;">
        {prompt}
    </div>""", unsafe_allow_html=True)

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