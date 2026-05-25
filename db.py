import sqlite3
import os
import json
from datetime import datetime

# Path database safely inside the writeable user AppData directory (resolves Program Files write permission errors)
APP_DATA_DIR = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "InboxHelper")
os.makedirs(APP_DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(APP_DATA_DIR, "inbox_helper.db")

def get_connection():
    """Returns a thread-safe connection to the SQLite database with row factory enabled."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initializes SQLite database tables if they do not exist."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Emails Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS emails (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message_id TEXT UNIQUE,
            subject TEXT,
            sender TEXT,
            date_sent TEXT,
            body_snippet TEXT,
            importance_score INTEGER,
            is_important INTEGER,
            classification_reason TEXT,
            is_read INTEGER DEFAULT 0,
            date_synced TEXT
        )
    """)
    
    # Logs Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            level TEXT,
            message TEXT
        )
    """)
    
    # App Settings/Tokens Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT UNIQUE,
            value TEXT
        )
    """)
    
    conn.commit()
    conn.close()

def get_setting(key: str, default: str = None) -> str:
    """Retrieves a configuration value from the SQLite settings table."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = cursor.fetchone()
        return row["value"] if row else default
    except Exception as e:
        print(f"Failed to fetch setting '{key}': {e}")
        return default
    finally:
        conn.close()

def set_setting(key: str, value: str):
    """Saves or updates a configuration value in the SQLite settings table."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            (key, str(value))
        )
        conn.commit()
    except Exception as e:
        log_event("ERROR", f"Failed to save setting '{key}': {e}")
    finally:
        conn.close()

def log_event(level: str, message: str):
    """Inserts a system event log into the local database and prints to standard output."""
    timestamp = datetime.now().isoformat()
    print(f"[{timestamp}] [{level.upper()}] {message}")
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO logs (timestamp, level, message) VALUES (?, ?, ?)",
            (timestamp, level, message)
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Failed to log event to database: {e}")

def insert_email(email_data: dict) -> bool:
    """
    Inserts a newly parsed email metadata block into the local SQLite database.
    Returns True if successfully inserted, False if it was a duplicate or error.
    """
    conn = get_connection()
    cursor = conn.cursor()
    timestamp = datetime.now().isoformat()
    
    try:
        cursor.execute(
            """
            INSERT OR IGNORE INTO emails (
                message_id, subject, sender, date_sent, body_snippet, 
                importance_score, is_important, classification_reason, is_read, date_synced
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                email_data["message_id"],
                email_data["subject"],
                email_data["sender"],
                email_data["date_sent"],
                email_data["body_snippet"],
                email_data["importance_score"],
                1 if email_data["is_important"] else 0,
                email_data["classification_reason"],
                1 if email_data["is_read"] else 0,
                timestamp
            )
        )
        success = cursor.rowcount > 0
        conn.commit()
        return success
    except Exception as e:
        log_event("ERROR", f"Failed to insert email {email_data.get('message_id')}: {e}")
        return False
    finally:
        conn.close()

def get_emails(limit: int = 100, only_important: bool = False):
    """Fetches list of synchronized emails sorted by reverse chronological order."""
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        if only_important:
            cursor.execute(
                "SELECT * FROM emails WHERE is_important = 1 ORDER BY date_sent DESC LIMIT ?",
                (limit,)
            )
        else:
            cursor.execute(
                "SELECT * FROM emails ORDER BY date_synced DESC LIMIT ?",
                (limit,)
            )
        
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    except Exception as e:
        log_event("ERROR", f"Failed to fetch emails: {e}")
        return []
    finally:
        conn.close()

def get_logs(limit: int = 150):
    """Fetches the latest execution logs from the database."""
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute(
            "SELECT * FROM logs ORDER BY id DESC LIMIT ?",
            (limit,)
        )
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    except Exception as e:
        print(f"Failed to fetch logs: {e}")
        return []
    finally:
        conn.close()

def update_read_status(message_id: str, is_read: bool):
    """Updates the read status of an email locally."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "UPDATE emails SET is_read = ? WHERE message_id = ?",
            (1 if is_read else 0, message_id)
        )
        conn.commit()
    except Exception as e:
        log_event("ERROR", f"Failed to update read status for {message_id}: {e}")
    finally:
        conn.close()

def clear_all_data():
    """Wipes the database tables clean."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM emails")
        cursor.execute("DELETE FROM logs")
        conn.commit()
        log_event("INFO", "Local database tables wiped clean successfully.")
    except Exception as e:
        log_event("ERROR", f"Failed to clear database: {e}")
    finally:
        conn.close()

# Initialize tables upon importing module
init_db()
