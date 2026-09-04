# -*- coding: utf-8 -*-
"""SQLite 存储层：面试会话 + 消息 + 评分"""
import json
import os
import sqlite3
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "interviewer.db")


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _connect():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    conn = _connect()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job TEXT NOT NULL DEFAULT '通用岗位',
                category TEXT NOT NULL DEFAULT 'general',
                level INTEGER NOT NULL DEFAULT 3,
                status TEXT NOT NULL DEFAULT 'active',
                score_json TEXT,
                summary TEXT,
                created_at TEXT NOT NULL,
                finished_at TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_created ON sessions(created_at)")
        conn.commit()
    finally:
        conn.close()


# ---------- sessions ----------

def create_session(job: str, category: str, level: int) -> int:
    conn = _connect()
    try:
        cur = conn.execute(
            "INSERT INTO sessions (job, category, level, created_at) VALUES (?, ?, ?, ?)",
            (job, category, level, _now()),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def get_session(session_id: int):
    conn = _connect()
    try:
        row = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
        return _session_dict(row) if row else None
    finally:
        conn.close()


def _session_dict(row):
    d = dict(row)
    d["score"] = json.loads(d.pop("score_json")) if d.get("score_json") else None
    return d


def list_sessions(page: int = 1, page_size: int = 10):
    conn = _connect()
    try:
        total = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
        rows = conn.execute(
            "SELECT * FROM sessions ORDER BY id DESC LIMIT ? OFFSET ?",
            (page_size, (page - 1) * page_size),
        ).fetchall()
        sessions = []
        for row in rows:
            d = _session_dict(row)
            cnt = conn.execute(
                "SELECT COUNT(*) FROM messages WHERE session_id = ?", (d["id"],)
            ).fetchone()[0]
            d["message_count"] = cnt
            sessions.append(d)
        return {"total": total, "sessions": sessions}
    finally:
        conn.close()


def finish_session(session_id: int, score: dict):
    conn = _connect()
    try:
        conn.execute(
            "UPDATE sessions SET status = 'finished', score_json = ?, summary = ?, finished_at = ? WHERE id = ?",
            (json.dumps(score, ensure_ascii=False), score.get("suggestion", ""), _now(), session_id),
        )
        conn.commit()
    finally:
        conn.close()


def reactivate_session(session_id: int):
    """已结束的会话被继续追问时：回到进行中，作废旧评分"""
    conn = _connect()
    try:
        conn.execute(
            "UPDATE sessions SET status = 'active', score_json = NULL, summary = '', finished_at = NULL WHERE id = ?",
            (session_id,),
        )
        conn.commit()
    finally:
        conn.close()


def delete_session(session_id: int) -> bool:
    conn = _connect()
    try:
        cur = conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        conn.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


# ---------- messages ----------

def add_message(session_id: int, role: str, content: str):
    conn = _connect()
    try:
        conn.execute(
            "INSERT INTO messages (session_id, role, content, created_at) VALUES (?, ?, ?, ?)",
            (session_id, role, content, _now()),
        )
        conn.commit()
    finally:
        conn.close()


def get_messages(session_id: int, limit: int = 60):
    """取最近 N 条消息（按时间正序返回，供对话使用）"""
    conn = _connect()
    try:
        rows = conn.execute(
            """
            SELECT role, content FROM (
                SELECT role, content, id FROM messages
                WHERE session_id = ? ORDER BY id DESC LIMIT ?
            ) ORDER BY id ASC
            """,
            (session_id, limit),
        ).fetchall()
        return [{"role": r["role"], "content": r["content"]} for r in rows]
    finally:
        conn.close()


def count_messages(session_id: int) -> int:
    conn = _connect()
    try:
        return conn.execute(
            "SELECT COUNT(*) FROM messages WHERE session_id = ?", (session_id,)
        ).fetchone()[0]
    finally:
        conn.close()
