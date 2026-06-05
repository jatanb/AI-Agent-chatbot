"""
database.py — SQLite with users, sessions, messages, saved schemes, deadline alerts
"""
import sqlite3
import json
import uuid
from datetime import datetime
from pathlib import Path

DB_PATH = Path("./data/govradar.db")


def get_conn():
    DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id           TEXT PRIMARY KEY,
            user_id      TEXT UNIQUE NOT NULL,
            name         TEXT NOT NULL,
            email        TEXT UNIQUE NOT NULL,
            password     TEXT NOT NULL,
            created_at   TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS sessions (
            id          TEXT PRIMARY KEY,
            user_id     TEXT NOT NULL,
            title       TEXT NOT NULL DEFAULT 'New chat',
            created_at  TEXT NOT NULL,
            updated_at  TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS messages (
            id          TEXT PRIMARY KEY,
            session_id  TEXT NOT NULL,
            role        TEXT NOT NULL,
            content     TEXT NOT NULL,
            created_at  TEXT NOT NULL,
            FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS saved_schemes (
            id          TEXT PRIMARY KEY,
            user_id     TEXT NOT NULL,
            title       TEXT NOT NULL,
            type        TEXT,
            description TEXT,
            deadline    TEXT,
            amount      TEXT,
            eligibility TEXT,
            ministry    TEXT,
            link        TEXT,
            alert_on    INTEGER DEFAULT 0,
            saved_at    TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS deadline_alerts (
            id          TEXT PRIMARY KEY,
            user_id     TEXT NOT NULL,
            scheme_id   TEXT NOT NULL,
            email       TEXT NOT NULL,
            alert_date  TEXT NOT NULL,
            sent        INTEGER DEFAULT 0,
            created_at  TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id);
        CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);
        CREATE INDEX IF NOT EXISTS idx_saved_user ON saved_schemes(user_id);
    """)
    conn.commit()
    conn.close()


# ── Users ─────────────────────────────────────────────────────────────────

def create_user(name: str, email: str, hashed_password: str) -> dict | None:
    try:
        conn = get_conn()
        uid = str(uuid.uuid4())[:12]
        now = datetime.now().isoformat()
        conn.execute(
            "INSERT INTO users (id, name, email, password, created_at) VALUES (?,?,?,?,?)",
            (uid, name, email.lower().strip(), hashed_password, now)
        )
        conn.commit()
        conn.close()
        return {"id": uid, "name": name, "email": email}
    except sqlite3.IntegrityError:
        return None  # email already exists


def get_user_by_email(email: str) -> dict | None:
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM users WHERE email=?", (email.lower().strip(),)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_user_by_id(user_id: str) -> dict | None:
    conn = get_conn()
    row = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


# ── Sessions ──────────────────────────────────────────────────────────────

def create_session(user_id: str, title="New chat") -> dict:
    conn = get_conn()
    now = datetime.now().isoformat()
    sid = str(uuid.uuid4())[:8]
    conn.execute(
        "INSERT INTO sessions (id, user_id, title, created_at, updated_at) VALUES (?,?,?,?,?)",
        (sid, user_id, title, now, now)
    )
    conn.commit()
    conn.close()
    return {"id": sid, "title": title, "created_at": now}


def get_user_sessions(user_id: str) -> list[dict]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM sessions WHERE user_id=? ORDER BY updated_at DESC",
        (user_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_session_title(session_id: str, title: str):
    conn = get_conn()
    now = datetime.now().isoformat()
    conn.execute(
        "UPDATE sessions SET title=?, updated_at=? WHERE id=?",
        (title, now, session_id)
    )
    conn.commit()
    conn.close()


def delete_session(session_id: str):
    conn = get_conn()
    conn.execute("DELETE FROM sessions WHERE id=?", (session_id,))
    conn.commit()
    conn.close()


# ── Messages ──────────────────────────────────────────────────────────────

def save_message(session_id: str, role: str, content) -> dict:
    conn = get_conn()
    now = datetime.now().isoformat()
    mid = str(uuid.uuid4())[:12]
    raw = json.dumps(content) if isinstance(content, dict) else content
    conn.execute(
        "INSERT INTO messages (id, session_id, role, content, created_at) VALUES (?,?,?,?,?)",
        (mid, session_id, role, raw, now)
    )
    conn.execute("UPDATE sessions SET updated_at=? WHERE id=?", (now, session_id))
    conn.commit()
    conn.close()
    return {"id": mid, "role": role, "content": content, "time": now[11:16]}


def get_messages(session_id: str) -> list[dict]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM messages WHERE session_id=? ORDER BY created_at ASC",
        (session_id,)
    ).fetchall()
    conn.close()
    msgs = []
    for r in rows:
        content = r["content"]
        try:
            content = json.loads(content)
        except (json.JSONDecodeError, TypeError):
            pass
        msgs.append({
            "id": r["id"],
            "role": r["role"],
            "content": content,
            "time": r["created_at"][11:16],
        })
    return msgs


# ── Saved schemes + Deadline alerts ──────────────────────────────────────

def save_scheme(user_id: str, scheme: dict, alert_on: bool = False) -> str:
    conn = get_conn()
    sid = str(uuid.uuid4())[:12]
    now = datetime.now().isoformat()
    conn.execute("""
        INSERT OR REPLACE INTO saved_schemes
        (id, user_id, title, type, description, deadline, amount,
         eligibility, ministry, link, alert_on, saved_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        sid, user_id,
        scheme.get("title",""),
        scheme.get("type",""),
        scheme.get("description",""),
        scheme.get("deadline",""),
        scheme.get("amount",""),
        scheme.get("eligibility",""),
        scheme.get("ministry",""),
        scheme.get("link",""),
        1 if alert_on else 0,
        now
    ))
    conn.commit()
    conn.close()
    return sid


def get_saved_schemes(user_id: str) -> list[dict]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM saved_schemes WHERE user_id=? ORDER BY saved_at DESC",
        (user_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_saved_scheme(scheme_id: str):
    conn = get_conn()
    conn.execute("DELETE FROM saved_schemes WHERE id=?", (scheme_id,))
    conn.commit()
    conn.close()


def create_alert(user_id: str, scheme_id: str, email: str, alert_date: str) -> str:
    conn = get_conn()
    aid = str(uuid.uuid4())[:12]
    now = datetime.now().isoformat()
    conn.execute("""
        INSERT INTO deadline_alerts (id, user_id, scheme_id, email, alert_date, sent, created_at)
        VALUES (?,?,?,?,?,0,?)
    """, (aid, user_id, scheme_id, email, alert_date, now))
    conn.commit()
    conn.close()
    return aid


def get_pending_alerts(today: str) -> list[dict]:
    """Called by scheduler — returns alerts due today or earlier, not yet sent."""
    conn = get_conn()
    rows = conn.execute("""
        SELECT da.*, ss.title, ss.deadline, u.name, u.email as user_email
        FROM deadline_alerts da
        JOIN saved_schemes ss ON da.scheme_id = ss.id
        JOIN users u ON da.user_id = u.id
        WHERE da.alert_date <= ? AND da.sent = 0
    """, (today,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def mark_alert_sent(alert_id: str):
    conn = get_conn()
    conn.execute("UPDATE deadline_alerts SET sent=1 WHERE id=?", (alert_id,))
    conn.commit()
    conn.close()


# Init on import
init_db()