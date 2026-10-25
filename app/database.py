import sqlite3
import os
from typing import Dict, Any

DATABASE_URL = os.getenv("DATABASE_URL")
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "gitpost.db")

def get_connection():
    if DATABASE_URL and DATABASE_URL.startswith("postgres"):
        try:
            import importlib
            psycopg = importlib.import_module("psycopg")
            dict_row = importlib.import_module("psycopg.rows").dict_row
            conn_str = DATABASE_URL.replace("postgres://", "postgresql://")
            return psycopg.connect(conn_str, row_factory=dict_row)
        except Exception:
            pass

    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout = 30000;")
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS monitored_repos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        repo_name TEXT UNIQUE,
        description TEXT,
        is_monitored INTEGER DEFAULT 0,
        is_private INTEGER DEFAULT 0,
        default_branch TEXT DEFAULT 'main',
        last_sha TEXT,
        last_checked_at TEXT,
        html_url TEXT,
        homepage_url TEXT,
        stars INTEGER DEFAULT 0,
        language TEXT,
        updated_at TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS posts_queue (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        repo_name TEXT,
        commit_sha TEXT,
        commit_message TEXT,
        commit_author TEXT,
        commit_url TEXT,
        post_content TEXT,
        media_url TEXT,
        media_type TEXT,
        media_title TEXT,
        status TEXT DEFAULT 'pending',
        approval_token TEXT UNIQUE,
        created_at TEXT,
        published_at TEXT,
        linkedin_post_id TEXT,
        error_message TEXT
    )
    """)

    columns_to_add = [
        ("monitored_repos", "homepage_url", "TEXT"),
        ("posts_queue", "media_url", "TEXT"),
        ("posts_queue", "media_type", "TEXT"),
        ("posts_queue", "media_title", "TEXT"),
    ]
    for table, col, col_type in columns_to_add:
        try:
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN {col} {col_type};")
        except Exception:
            pass

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS processed_commits (
        sha TEXT PRIMARY KEY,
        repo_name TEXT,
        processed_at TEXT
    )
    """)

    default_settings = {
        "github_token": "",
        "github_username": "",
        "smtp_host": "smtp.gmail.com",
        "smtp_port": "587",
        "smtp_user": "",
        "smtp_pass": "",
        "smtp_from": "",
        "email_recipient": "",
        "linkedin_access_token": "",
        "linkedin_person_urn": "",
        "linkedin_simulation_mode": "1",
        "gemini_api_key": "",
        "ai_tone": "Profissional e Engajador",
        "ai_custom_instructions": "Foque no aprendizado prático, tecnologias usadas e impacto do projeto.",
        "check_interval_minutes": "5",
        "app_base_url": "http://localhost:8000"
    }

    for k, v in default_settings.items():
        cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (k, v))

    conn.commit()
    conn.close()

def get_setting(key: str, default: str = "") -> str:
    conn = get_connection()
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    conn.close()
    return row["value"] if row and row["value"] is not None else default

def get_all_settings() -> Dict[str, str]:
    conn = get_connection()
    rows = conn.execute("SELECT key, value FROM settings").fetchall()
    conn.close()
    return {r["key"]: (r["value"] or "") for r in rows}

def set_setting(key: str, value: str):
    conn = get_connection()
    conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))
    conn.commit()
    conn.close()

def update_settings(data: Dict[str, Any]):
    conn = get_connection()
    for k, v in data.items():
        conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (k, str(v) if v is not None else ""))
    conn.commit()
    conn.close()
