"""
src/auth/auth.py — Login, Register, Session management
Uses bcrypt for password hashing — never store plain text passwords
"""
import bcrypt
import streamlit as st
from src.database.database import create_user, get_user_by_email


# ── Password helpers ──────────────────────────────────────────────────────

def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


# ── Session helpers ───────────────────────────────────────────────────────

def login_user(user: dict):
    """Store user in Streamlit session after successful login."""
    st.session_state.user = {
        "id":    user["id"],
        "name":  user["name"],
        "email": user["email"],
    }
    st.session_state.current_session = None


def logout_user():
    for key in ["user", "current_session", "editing", "edit_text"]:
        st.session_state.pop(key, None)


def current_user() -> dict | None:
    return st.session_state.get("user", None)


def is_logged_in() -> bool:
    return current_user() is not None


# ── Register ──────────────────────────────────────────────────────────────

def register(name: str, email: str, password: str) -> tuple[bool, str]:
    """
    Returns (success, message)
    """
    name  = name.strip()
    email = email.strip().lower()

    if not name or not email or not password:
        return False, "All fields are required."
    if len(password) < 6:
        return False, "Password must be at least 6 characters."
    if "@" not in email:
        return False, "Enter a valid email address."

    hashed = hash_password(password)
    user   = create_user(name, email, hashed)

    if user is None:
        return False, "Email already registered. Please log in."

    login_user(user)
    return True, f"Welcome, {name}!"


# ── Login ─────────────────────────────────────────────────────────────────

def login(email: str, password: str) -> tuple[bool, str]:
    """
    Returns (success, message)
    """
    email = email.strip().lower()

    if not email or not password:
        return False, "Email and password are required."

    user = get_user_by_email(email)

    if user is None:
        return False, "No account found with this email."

    if not verify_password(password, user["password"]):
        return False, "Incorrect password."

    login_user(user)
    return True, f"Welcome back, {user['name']}!"