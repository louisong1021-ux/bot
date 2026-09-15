import os
import sqlite3
from contextlib import closing
from datetime import datetime, timezone

DB_PATH = os.getenv("DB_PATH", "data/sms_receptionist.db")


def _utc_now():
    return datetime.now(timezone.utc).isoformat()


def _connect():
    directory = os.path.dirname(DB_PATH)
    if directory:
        os.makedirs(directory, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=20)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with closing(_connect()) as conn:
        conn.executescript(
            """
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                phone TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
                body TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_messages_phone_id
            ON messages(phone, id);

            CREATE TABLE IF NOT EXISTS inbound_requests (
                message_sid TEXT PRIMARY KEY,
                phone TEXT NOT NULL,
                body TEXT NOT NULL,
                reply_body TEXT,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS contacts (
                phone TEXT PRIMARY KEY,
                opted_out INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS leads (
                phone TEXT PRIMARY KEY,
                name TEXT,
                company TEXT,
                industry TEXT,
                need TEXT,
                preferred_callback TEXT,
                summary TEXT,
                score TEXT NOT NULL DEFAULT 'cold',
                human_handoff INTEGER NOT NULL DEFAULT 0,
                notion_page_id TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """
        )
        conn.commit()


def get_cached_reply(message_sid):
    if not message_sid:
        return None
    with closing(_connect()) as conn:
        row = conn.execute(
            "SELECT reply_body FROM inbound_requests WHERE message_sid = ?",
            (message_sid,)
        ).fetchone()
        return row["reply_body"] if row and row["reply_body"] is not None else None


def cache_inbound(message_sid, phone, body, reply_body=None):
    if not message_sid:
        return
    now = _utc_now()
    with closing(_connect()) as conn:
        conn.execute(
            """
            INSERT INTO inbound_requests(message_sid, phone, body, reply_body, created_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(message_sid) DO UPDATE SET
                reply_body = COALESCE(excluded.reply_body, inbound_requests.reply_body)
            """,
            (message_sid, phone, body, reply_body, now)
        )
        conn.commit()


def save_message(phone, role, body):
    with closing(_connect()) as conn:
        conn.execute(
            "INSERT INTO messages(phone, role, body, created_at) VALUES (?, ?, ?, ?)",
            (phone, role, body, _utc_now())
        )
        conn.commit()


def get_history(phone, limit=16):
    with closing(_connect()) as conn:
        rows = conn.execute(
            """
            SELECT role, body
            FROM messages
            WHERE phone = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (phone, limit)
        ).fetchall()
    rows = list(reversed(rows))
    return [{"role": row["role"], "content": row["body"]} for row in rows]


def set_opt_out(phone, opted_out):
    now = _utc_now()
    with closing(_connect()) as conn:
        conn.execute(
            """
            INSERT INTO contacts(phone, opted_out, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(phone) DO UPDATE SET
                opted_out = excluded.opted_out,
                updated_at = excluded.updated_at
            """,
            (phone, 1 if opted_out else 0, now)
        )
        conn.commit()


def is_opted_out(phone):
    with closing(_connect()) as conn:
        row = conn.execute(
            "SELECT opted_out FROM contacts WHERE phone = ?",
            (phone,)
        ).fetchone()
        return bool(row["opted_out"]) if row else False


def upsert_lead(phone, lead, human_handoff=False):
    now = _utc_now()
    with closing(_connect()) as conn:
        existing = conn.execute(
            "SELECT * FROM leads WHERE phone = ?",
            (phone,)
        ).fetchone()

        created_at = existing["created_at"] if existing else now
        notion_page_id = existing["notion_page_id"] if existing else None

        def merged(field, default=None):
            value = lead.get(field)
            if value not in (None, ""):
                return value
            if existing:
                return existing[field]
            return default

        conn.execute(
            """
            INSERT INTO leads(
                phone, name, company, industry, need, preferred_callback,
                summary, score, human_handoff, notion_page_id, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(phone) DO UPDATE SET
                name = excluded.name,
                company = excluded.company,
                industry = excluded.industry,
                need = excluded.need,
                preferred_callback = excluded.preferred_callback,
                summary = excluded.summary,
                score = excluded.score,
                human_handoff = excluded.human_handoff,
                updated_at = excluded.updated_at
            """,
            (
                phone,
                merged("name"),
                merged("company"),
                merged("industry"),
                merged("need"),
                merged("preferred_callback"),
                merged("summary"),
                merged("score", "cold"),
                1 if human_handoff else (existing["human_handoff"] if existing else 0),
                notion_page_id,
                created_at,
                now
            )
        )
        conn.commit()


def get_lead(phone):
    with closing(_connect()) as conn:
        row = conn.execute("SELECT * FROM leads WHERE phone = ?", (phone,)).fetchone()
        return dict(row) if row else None


def mark_notion_page(phone, notion_page_id):
    with closing(_connect()) as conn:
        conn.execute(
            "UPDATE leads SET notion_page_id = ?, updated_at = ? WHERE phone = ?",
            (notion_page_id, _utc_now(), phone)
        )
        conn.commit()
