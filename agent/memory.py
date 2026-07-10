import sqlite3
import json
import os
from datetime import datetime

MEMORY_DB = "sample_data/memory.db"


def init_memory_db():
    os.makedirs("sample_data", exist_ok=True)
    conn = sqlite3.connect(MEMORY_DB)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id  TEXT NOT NULL,
            role        TEXT NOT NULL,
            content     TEXT NOT NULL,
            sql_query   TEXT,
            timestamp   TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS query_log (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id  TEXT,
            question    TEXT,
            sql_query   TEXT,
            row_count   INTEGER,
            success     INTEGER,
            timestamp   TEXT
        )
    """)
    conn.commit()
    conn.close()


def save_message(session_id: str, role: str, content: str, sql_query: str = None):
    conn = sqlite3.connect(MEMORY_DB)
    conn.execute(
        "INSERT INTO conversations (session_id, role, content, sql_query, timestamp) VALUES (?,?,?,?,?)",
        (session_id, role, content, sql_query, datetime.now().isoformat())
    )
    conn.commit()
    conn.close()


def get_history(session_id: str, limit: int = 10) -> list:
    conn = sqlite3.connect(MEMORY_DB)
    rows = conn.execute(
        """SELECT role, content FROM conversations WHERE session_id = ? ORDER BY id DESC LIMIT ?""",
        (session_id, limit)
    ).fetchall()
    conn.close()
    return [{"role": r[0], "content": r[1]} for r in reversed(rows)]


def log_query(session_id, question, sql_query, row_count, success):
    conn = sqlite3.connect(MEMORY_DB)
    conn.execute(
        "INSERT INTO query_log (session_id,question,sql_query,row_count,success,timestamp) VALUES (?,?,?,?,?,?)",
        (session_id, question, sql_query, row_count, int(success), datetime.now().isoformat())
    )
    conn.commit()
    conn.close()


def get_query_log(limit: int = 20) -> list:
    conn = sqlite3.connect(MEMORY_DB)
    rows = conn.execute(
        "SELECT question, sql_query, row_count, success, timestamp FROM query_log ORDER BY id DESC LIMIT ?",
        (limit,)
    ).fetchall()
    conn.close()
    return [
        {"question": r[0], "sql": r[1], "rows": r[2], "success": bool(r[3]), "time": r[4]}
        for r in rows
    ]


init_memory_db()