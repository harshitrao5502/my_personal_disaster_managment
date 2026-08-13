import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

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
    conn.execute("""
        CREATE TABLE IF NOT EXISTS calls (
            call_id TEXT PRIMARY KEY,
            user_id TEXT,
            started_at TEXT,
            ended_at TEXT,
            outcome TEXT,
            channel TEXT
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


def save_caller(
    user_id: str,
    name: Optional[str] = None,
    language_preference: Optional[str] = None,
    facts: Optional[dict] = None,
):
    existing = get_caller(user_id)
    merged_facts = existing["facts"] if existing else {}
    if facts:
        merged_facts.update(facts)

    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        INSERT INTO callers (user_id, name, language_preference, facts, last_interaction)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            name = COALESCE(excluded.name, callers.name),
            language_preference = COALESCE(excluded.language_preference, callers.language_preference),
            facts = excluded.facts,
            last_interaction = excluded.last_interaction
    """,
        (
            user_id,
            name or (existing["name"] if existing else None),
            language_preference
            or (existing["language_preference"] if existing else None),
            json.dumps(merged_facts),
            datetime.now(timezone.utc).isoformat(),
        ),
    )
    conn.commit()
    conn.close()


def delete_caller(user_id: str):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("DELETE FROM callers WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()


def start_call_record(call_id: str, user_id: str, channel: str):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        INSERT INTO calls (call_id, user_id, started_at, ended_at, outcome, channel)
        VALUES (?, ?, ?, NULL, 'failed', ?)
    """,
        (call_id, user_id, datetime.now(timezone.utc).isoformat(), channel),
    )
    conn.commit()
    conn.close()


def mark_call_outcome(call_id: str, outcome: str):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        UPDATE calls
        SET ended_at = ?, outcome = ?
        WHERE call_id = ?
    """,
        (datetime.now(timezone.utc).isoformat(), outcome, call_id),
    )
    conn.commit()
    conn.close()


def get_call_stats():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM calls")
    total_calls = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM calls WHERE outcome = 'success'")
    successful_calls = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM calls WHERE outcome = 'failed'")
    failed_calls = cursor.fetchone()[0]

    cursor.execute("""
        SELECT call_id, started_at, ended_at, outcome, channel
        FROM calls
        ORDER BY started_at DESC
        LIMIT 10
    """)
    rows = cursor.fetchall()
    recent_calls = []
    for r in rows:
        recent_calls.append(
            {
                "call_id": r[0][:8] if r[0] else "",
                "started_at": r[1],
                "ended_at": r[2],
                "outcome": r[3],
                "channel": r[4],
            }
        )

    conn.close()
    return {
        "total_calls": total_calls,
        "successful_calls": successful_calls,
        "failed_calls": failed_calls,
        "recent_calls": recent_calls,
    }
