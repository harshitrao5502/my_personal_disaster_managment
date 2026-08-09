import sqlite3
import json
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).parent / "raksha_memory.db"


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS callers (
            user_id TEXT PRIMARY KEY,
            name TEXT,
            language_preference TEXT,
            facts TEXT,
            last_interaction TEXT
        )
    """)
    conn.commit()
    conn.close()


def get_caller(user_id: str):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM callers WHERE user_id = ?", (user_id,)).fetchone()
    conn.close()
    if row is None:
        return None
    return {
        "user_id": row["user_id"],
        "name": row["name"],
        "language_preference": row["language_preference"],
        "facts": json.loads(row["facts"]) if row["facts"] else {},
        "last_interaction": row["last_interaction"],
    }


def save_caller(user_id: str, name: str = None, language_preference: str = None, facts: dict = None):
    existing = get_caller(user_id)
    merged_facts = existing["facts"] if existing else {}
    if facts:
        merged_facts.update(facts)

    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        INSERT INTO callers (user_id, name, language_preference, facts, last_interaction)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            name = COALESCE(excluded.name, callers.name),
            language_preference = COALESCE(excluded.language_preference, callers.language_preference),
            facts = excluded.facts,
            last_interaction = excluded.last_interaction
    """, (
        user_id,
        name or (existing["name"] if existing else None),
        language_preference or (existing["language_preference"] if existing else None),
        json.dumps(merged_facts),
        datetime.now(timezone.utc).isoformat(),
    ))
    conn.commit()
    conn.close()


def delete_caller(user_id: str):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("DELETE FROM callers WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()