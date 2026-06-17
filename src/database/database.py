import os
import json
import uuid
from datetime import datetime
from dotenv import load_dotenv

from sqlalchemy import (
    create_engine, text, Column, String, Text,
    Integer, ForeignKey, Index
)
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from sqlalchemy.pool import NullPool

load_dotenv()

# ── Engine setup ──────────────────────────────────────────────────────────
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/new.db")

# Render gives postgres:// but SQLAlchemy needs postgresql://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# SQLite needs check_same_thread=False, PostgreSQL needs NullPool for Streamlit
if DATABASE_URL.startswith("sqlite"):
    import os
    os.makedirs("./data", exist_ok=True)
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False}
    )
else:
    engine = create_engine(
        DATABASE_URL,
        poolclass=NullPool   # important for Streamlit — no connection pooling issues
    )

SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()


# ── Models ────────────────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"
    id         = Column(String, primary_key=True, default=lambda: str(uuid.uuid4())[:12])
    name       = Column(String, nullable=False)
    email      = Column(String, unique=True, nullable=False)
    password   = Column(String, nullable=False)
    created_at = Column(String, nullable=False)


class ChatSession(Base):
    __tablename__ = "sessions"
    id         = Column(String, primary_key=True, default=lambda: str(uuid.uuid4())[:8])
    user_id    = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title      = Column(String, default="New chat")
    created_at = Column(String, nullable=False)
    updated_at = Column(String, nullable=False)


class Message(Base):
    __tablename__ = "messages"
    id         = Column(String, primary_key=True, default=lambda: str(uuid.uuid4())[:12])
    session_id = Column(String, ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False)
    role       = Column(String, nullable=False)
    content    = Column(Text, nullable=False)
    created_at = Column(String, nullable=False)


class SavedScheme(Base):
    __tablename__ = "saved_schemes"
    id          = Column(String, primary_key=True, default=lambda: str(uuid.uuid4())[:12])
    user_id     = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title       = Column(String, nullable=False)
    type        = Column(String)
    description = Column(Text)
    deadline    = Column(String)
    amount      = Column(String)
    eligibility = Column(String)
    ministry    = Column(String)
    link        = Column(String)
    alert_on    = Column(Integer, default=0)
    saved_at    = Column(String, nullable=False)


class DeadlineAlert(Base):
    __tablename__ = "deadline_alerts"
    id         = Column(String, primary_key=True, default=lambda: str(uuid.uuid4())[:12])
    user_id    = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    scheme_id  = Column(String, nullable=False)
    email      = Column(String, nullable=False)
    alert_date = Column(String, nullable=False)
    sent       = Column(Integer, default=0)
    created_at = Column(String, nullable=False)


def init_db():
    """Create all tables if they don't exist."""
    Base.metadata.create_all(bind=engine)

def get_db() -> Session:
    return SessionLocal()


# Init on import
init_db()


# ── Users ─────────────────────────────────────────────────────────────────

def create_user(name: str, email: str, hashed_password: str) -> dict | None:
    db = get_db()
    try:
        now = datetime.now().isoformat()
        user = User(
            id=str(uuid.uuid4())[:12],
            name=name,
            email=email.lower().strip(),
            password=hashed_password,
            created_at=now
        )
        db.add(user)
        db.commit()
        return {"id": user.id, "name": name, "email": email}
    except Exception:
        db.rollback()
        return None  # email already exists
    finally:
        db.close()


def get_user_by_email(email: str) -> dict | None:
    db = get_db()
    try:
        user = db.query(User).filter(User.email == email.lower().strip()).first()
        if not user:
            return None
        return {"id": user.id, "name": user.name,
                "email": user.email, "password": user.password}
    finally:
        db.close()


def get_user_by_id(user_id: str) -> dict | None:
    db = get_db()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return None
        return {"id": user.id, "name": user.name, "email": user.email}
    finally:
        db.close()


# ── Sessions ──────────────────────────────────────────────────────────────

def create_session(user_id: str, title: str = "New chat") -> dict:
    db = get_db()
    try:
        now = datetime.now().isoformat()
        sess = ChatSession(
            id=str(uuid.uuid4())[:8],
            user_id=user_id,
            title=title,
            created_at=now,
            updated_at=now
        )
        db.add(sess)
        db.commit()
        return {"id": sess.id, "title": title, "created_at": now}
    finally:
        db.close()


def get_user_sessions(user_id: str) -> list[dict]:
    db = get_db()
    try:
        sessions = (db.query(ChatSession)
                    .filter(ChatSession.user_id == user_id)
                    .order_by(ChatSession.updated_at.desc())
                    .all())
        return [{"id": s.id, "title": s.title, "created_at": s.created_at}
                for s in sessions]
    finally:
        db.close()


def update_session_title(session_id: str, title: str):
    db = get_db()
    try:
        now = datetime.now().isoformat()
        db.query(ChatSession).filter(ChatSession.id == session_id).update(
            {"title": title, "updated_at": now}
        )
        db.commit()
    finally:
        db.close()


def delete_session(session_id: str):
    db = get_db()
    try:
        db.query(Message).filter(Message.session_id == session_id).delete()
        db.query(ChatSession).filter(ChatSession.id == session_id).delete()
        db.commit()
    finally:
        db.close()


# ── Messages ──────────────────────────────────────────────────────────────

def save_message(session_id: str, role: str, content) -> dict:
    db = get_db()
    try:
        now = datetime.now().isoformat()
        mid = str(uuid.uuid4())[:12]
        raw = json.dumps(content) if isinstance(content, dict) else str(content)
        msg = Message(
            id=mid,
            session_id=session_id,
            role=role,
            content=raw,
            created_at=now
        )
        db.add(msg)
        # Update session updated_at
        db.query(ChatSession).filter(ChatSession.id == session_id).update(
            {"updated_at": now}
        )
        db.commit()
        return {"id": mid, "role": role, "content": content, "time": now[11:16]}
    finally:
        db.close()


def get_messages(session_id: str) -> list[dict]:
    db = get_db()
    try:
        msgs = (db.query(Message)
                .filter(Message.session_id == session_id)
                .order_by(Message.created_at.asc())
                .all())
        result = []
        for m in msgs:
            content = m.content
            try:
                content = json.loads(content)
            except (json.JSONDecodeError, TypeError):
                pass
            result.append({
                "id": m.id,
                "role": m.role,
                "content": content,
                "time": m.created_at[11:16],
            })
        return result
    finally:
        db.close()


# ── Saved schemes ─────────────────────────────────────────────────────────

def save_scheme(user_id: str, scheme: dict, alert_on: bool = False) -> str:
    db = get_db()
    try:
        now = datetime.now().isoformat()
        sid = str(uuid.uuid4())[:12]
        s = SavedScheme(
            id=sid, user_id=user_id,
            title=scheme.get("title", ""),
            type=scheme.get("type", ""),
            description=scheme.get("description", ""),
            deadline=scheme.get("deadline", ""),
            amount=scheme.get("amount", ""),
            eligibility=scheme.get("eligibility", ""),
            ministry=scheme.get("ministry", ""),
            link=scheme.get("link", ""),
            alert_on=1 if alert_on else 0,
            saved_at=now
        )
        db.add(s)
        db.commit()
        return sid
    finally:
        db.close()


def get_saved_schemes(user_id: str) -> list[dict]:
    db = get_db()
    try:
        schemes = (db.query(SavedScheme)
                   .filter(SavedScheme.user_id == user_id)
                   .order_by(SavedScheme.saved_at.desc())
                   .all())
        return [{
            "id": s.id, "title": s.title, "type": s.type,
            "description": s.description, "deadline": s.deadline,
            "amount": s.amount, "eligibility": s.eligibility,
            "ministry": s.ministry, "link": s.link,
        } for s in schemes]
    finally:
        db.close()


def delete_saved_scheme(scheme_id: str):
    db = get_db()
    try:
        db.query(SavedScheme).filter(SavedScheme.id == scheme_id).delete()
        db.commit()
    finally:
        db.close()


# ── Deadline alerts ───────────────────────────────────────────────────────

def create_alert(user_id: str, scheme_id: str, email: str, alert_date: str) -> str:
    db = get_db()
    try:
        now = datetime.now().isoformat()
        aid = str(uuid.uuid4())[:12]
        alert = DeadlineAlert(
            id=aid, user_id=user_id, scheme_id=scheme_id,
            email=email, alert_date=alert_date, sent=0, created_at=now
        )
        db.add(alert)
        db.commit()
        return aid
    finally:
        db.close()


def get_pending_alerts(today: str) -> list[dict]:
    db = get_db()
    try:
        alerts = (db.query(DeadlineAlert)
                  .filter(DeadlineAlert.alert_date <= today,
                          DeadlineAlert.sent == 0)
                  .all())
        return [{"id": a.id, "email": a.email,
                 "scheme_id": a.scheme_id, "alert_date": a.alert_date}
                for a in alerts]
    finally:
        db.close()


def mark_alert_sent(alert_id: str):
    db = get_db()
    try:
        db.query(DeadlineAlert).filter(DeadlineAlert.id == alert_id).update({"sent": 1})
        db.commit()
    finally:
        db.close()