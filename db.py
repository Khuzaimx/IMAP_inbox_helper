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
    
    # Inbox TL;DR Digests Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS digests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            digest_date TEXT UNIQUE,
            summary_content TEXT,
            action_items TEXT,
            created_at TEXT
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

def has_matching_thread(core_subject: str) -> bool:
    """
    Checks if there is already an existing email in the local database that has the 
    same core subject (after cleaning out Re: / Fwd: prefixes).
    This helps the classifier detect ongoing conversations.
    """
    if not core_subject or len(core_subject.strip()) < 3:
        return False
        
    conn = get_connection()
    cursor = conn.cursor()
    try:
        # Search for subject containing the core thread subject
        cursor.execute(
            "SELECT 1 FROM emails WHERE subject LIKE ? OR ? LIKE '%' || subject || '%' LIMIT 1",
            (f"%{core_subject}%", core_subject)
        )
        row = cursor.fetchone()
        return row is not None
    except Exception as e:
        print(f"Failed to check thread match for '{core_subject}': {e}")
        return False
    finally:
        conn.close()

def save_digest(digest_date: str, summary_content: str, action_items: str) -> bool:
    """Saves or updates a daily digest JSON payload in the SQLite digests table."""
    conn = get_connection()
    cursor = conn.cursor()
    created_at = datetime.now().isoformat()
    try:
        cursor.execute(
            """
            INSERT OR REPLACE INTO digests (digest_date, summary_content, action_items, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (digest_date, summary_content, action_items, created_at)
        )
        conn.commit()
        return True
    except Exception as e:
        log_event("ERROR", f"Failed to save digest for date '{digest_date}': {e}")
        return False
    finally:
        conn.close()

def get_latest_digest():
    """Retrieves the most recently generated daily digest row from SQLite."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT * FROM digests ORDER BY digest_date DESC LIMIT 1"
        )
        row = cursor.fetchone()
        return dict(row) if row else None
    except Exception as e:
        log_event("ERROR", f"Failed to fetch latest digest: {e}")
        return None
    finally:
        conn.close()

def get_digest_by_date(date_str: str):
    """Retrieves a specific daily digest row from SQLite based on date string (YYYY-MM-DD)."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT * FROM digests WHERE digest_date = ?",
            (date_str,)
        )
        row = cursor.fetchone()
        return dict(row) if row else None
    except Exception as e:
        log_event("ERROR", f"Failed to fetch digest for date '{date_str}': {e}")
        return None
    finally:
        conn.close()

def toggle_digest_action(date_str: str, task_text: str, is_completed: bool) -> bool:
    """Updates the completion state of a specific task inside the daily digest JSON block."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        # 1. Fetch current digest
        cursor.execute("SELECT action_items FROM digests WHERE digest_date = ?", (date_str,))
        row = cursor.fetchone()
        if not row:
            return False
            
        action_items = json.loads(row["action_items"])
        # 2. Find and update the task
        for item in action_items:
            if item["task"] == task_text:
                item["completed"] = is_completed
                break
                
        # 3. Save back to SQLite
        cursor.execute(
            "UPDATE digests SET action_items = ? WHERE digest_date = ?",
            (json.dumps(action_items), date_str)
        )
        conn.commit()
        return True
    except Exception as e:
        log_event("ERROR", f"Failed to toggle action item in digest: {e}")
        return False
    finally:
        conn.close()

def clear_all_data():
    """Wipes the database tables clean."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM emails")
        cursor.execute("DELETE FROM logs")
        cursor.execute("DELETE FROM digests")
        conn.commit()
        log_event("INFO", "Local database tables wiped clean successfully.")
    except Exception as e:
        log_event("ERROR", f"Failed to clear database: {e}")
    finally:
        conn.close()

# Initialize tables upon importing module
init_db()
