"""
src/components/auth.py
Login and register page rendering.
"""
import streamlit as st
from src.auth.auth import login, register


def render_auth_page():
    _, col, _ = st.columns([1, 2, 1])
    with col:
        st.markdown(
    """
    <h1 style='text-align:center; margin-bottom:10px;color:white'>
        Login here
    </h1>
    """,
    unsafe_allow_html=True)
        
        st.divider()

        c1, c2 = st.columns(2)
        with c1:
            if st.button("Login", use_container_width=True,
                         type="primary" if st.session_state.auth_mode == "login" else "secondary",
                         key="mode_login"):
                st.session_state.auth_mode = "login"
                st.rerun()
        with c2:
            if st.button("Register", use_container_width=True,
                         type="primary" if st.session_state.auth_mode == "register" else "secondary",
                         key="mode_reg"):
                st.session_state.auth_mode = "register"
                st.rerun()


        if st.session_state.auth_mode == "login":
            with st.form("login_form"):
                email    = st.text_input("Email", placeholder="you@email.com")
                password = st.text_input("Password", type="password", placeholder="••••••••")
                if st.form_submit_button("Login", use_container_width=True):
                    if not email or not password:
                        st.error("Please fill in all fields.")
                    else:
                        ok, msg = login(email, password)
                        if ok: st.rerun()
                        else: st.error(msg)
        else:
            with st.form("register_form"):
                name     = st.text_input("Full name", placeholder="Your name")
                email    = st.text_input("Email", placeholder="you@email.com")
                password = st.text_input("Password", type="password", placeholder="Min 6 characters")
                if st.form_submit_button("Create account", use_container_width=True):
                    if not name or not email or not password:
                        st.error("Please fill in all fields.")
                    else:
                        ok, msg = register(name, email, password)
                        if ok: st.rerun()
                        else: st.error(msg)

    st.stop()