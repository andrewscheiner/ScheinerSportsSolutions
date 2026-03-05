import sqlite3
from pathlib import Path

DB_PATH = Path("users.db")

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            ID TEXT PRIMARY KEY,
            Email TEXT NOT NULL,
            Name TEXT,
            CreatedDate TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    return conn

def upsert_user(google_id, email, name=None):
    conn = get_conn()
    conn.execute("""
        INSERT INTO users (ID, Email, Name, CreatedDate)
        VALUES (?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(ID) DO UPDATE SET
            Email=excluded.Email,
            Name=excluded.Name
    """, (google_id, email, name))
    conn.commit()
    conn.close()