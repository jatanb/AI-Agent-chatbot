import streamlit as st
from src.auth.auth import is_logged_in, current_user
from src.database.database import create_session, get_user_sessions
from src.components.auth import render_auth_page
from src.components.sidebar import render_sidebar
from src.components.chat import render_chat_page
from src.components.resume_page import render_resume_page

st.set_page_config(
    page_title="Scheme Scout",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── Session state ───────────────────
for k, v in {
    "current_session": None, "editing": None, "edit_text": "",
    "active_tab": "chat", "auth_mode": "login",
    "resume_profile": None, "resume_name": "", "show_optimizer": False,
}.items():
    if k not in st.session_state:
        st.session_state[k] = v


# ── Auth gate ─────────────────────────────────────────────────────────────
if not is_logged_in():
    render_auth_page()


# ── Logged in ─────────────────────────────────────────────────────────────
user = current_user()
if not user:
    st.session_state.clear()
    st.rerun()


def ensure_session(user_id):
    if not st.session_state.current_session:
        sessions = get_user_sessions(user_id)
        st.session_state.current_session = (
            sessions[0]["id"] if sessions else create_session(user_id)["id"]
        )

ensure_session(user["id"])

# ── Sidebar ───────────────────────────────────────────────────────────────
render_sidebar(user, ensure_session)

# ── Page routing ──────────────────────────────────────────────────────────
if st.session_state.active_tab == "resume":
    render_resume_page(user)

else:
    render_chat_page()