"""
src/components/sidebar.py
Sidebar rendering.
"""
import streamlit as st
from src.auth.auth import logout_user
from src.database.database import create_session, get_user_sessions, delete_session


def render_sidebar(user, ensure_session_fn):
    with st.sidebar:
        st.markdown("**Recents**")
        st.caption(user["name"])
        st.divider()

        if st.button("＋  New chat", use_container_width=True, key="new_chat"):
            sess = create_session(user["id"])
            st.session_state.current_session = sess["id"]
            st.session_state.active_tab = "chat"
            st.rerun()

        if st.button("📄  Resume Search", use_container_width=True, key="nav_resume"):
            st.session_state.active_tab = "resume"
            st.rerun()

        st.divider()

        sessions = get_user_sessions(user["id"])
        if not sessions:
            st.caption("No chats yet")
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
                    ensure_session_fn(user["id"])
                    st.rerun()

        st.divider()
        st.caption("Gemini · LangGraph · Tavily")
        if st.button("Logout", use_container_width=True, key="logout"):
            logout_user()
            st.rerun()