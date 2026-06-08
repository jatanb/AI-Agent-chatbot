"""
src/ui/login_page.py — Login page design only
"""
import streamlit as st


def login_header():
    st.markdown("""
    <div style="text-align:center;padding:3rem 0 2.5rem;">
        <div style="font-size:28px;font-weight:600;color:#eee;
                    letter-spacing:-0.03em;margin-bottom:6px;">
            🔍 Scheme Scout
        </div>
        <div style="font-size:13px;color:#444;font-weight:400;line-height:1.6;">
            Find Indian government scholarships,<br>internships and schemes instantly.
        </div>
    </div>""", unsafe_allow_html=True)


def login_form():
    """Renders email/password login inputs. Returns (email, password, submitted)."""
    with st.form("login_form", clear_on_submit=False):
        email    = st.text_input("Email", placeholder="you@email.com")
        password = st.text_input("Password", type="password", placeholder="••••••••")
        st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
        submitted = st.form_submit_button("Login", use_container_width=True)
    return email, password, submitted


def register_form():
    """Renders register inputs. Returns (name, email, password, submitted)."""
    with st.form("register_form", clear_on_submit=False):
        name     = st.text_input("Full name", placeholder="Your name")
        email    = st.text_input("Email", placeholder="you@email.com")
        password = st.text_input("Password", type="password", placeholder="Min 6 characters")
        st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
        submitted = st.form_submit_button("Create account", use_container_width=True)
    return name, email, password, submitted


def auth_toggle(current_mode):
    """Renders Login/Register toggle buttons. Returns clicked mode or None."""
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Login", use_container_width=True,
                     type="primary" if current_mode == "login" else "secondary",
                     key="mode_login"):
            return "login"
    with c2:
        if st.button("Register", use_container_width=True,
                     type="primary" if current_mode == "register" else "secondary",
                     key="mode_reg"):
            return "register"
    return None