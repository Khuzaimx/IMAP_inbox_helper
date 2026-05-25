import os
from dotenv import load_dotenv
# Path settings configuration file safely inside the writeable user AppData directory
APP_DATA_DIR = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "InboxHelper")
os.makedirs(APP_DATA_DIR, exist_ok=True)
ENV_PATH = os.path.join(APP_DATA_DIR, ".env")

# Load variables from writeable AppData .env file
load_dotenv(ENV_PATH)

class Config:
    # IMAP Configuration
    IMAP_HOST = os.getenv("IMAP_HOST", "imap.gmail.com")
    IMAP_PORT = int(os.getenv("IMAP_PORT", 993))
    IMAP_SSL = os.getenv("IMAP_SSL", "True").lower() in ("true", "1", "yes")
    IMAP_USER = os.getenv("IMAP_USER", "")
    IMAP_PASSWORD = os.getenv("IMAP_PASSWORD", "")

    # Monitoring Setup
    MONITOR_FOLDER = os.getenv("MONITOR_FOLDER", "INBOX")
    POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", 300))

    # Scoring Engine
    IMPORTANCE_THRESHOLD = int(os.getenv("IMPORTANCE_THRESHOLD", 50))

    # Custom Rules (Parsed into Lists)
    WHITELIST_SENDERS = [
        email.strip().lower()
        for email in os.getenv("WHITELIST_SENDERS", "").split(",")
        if email.strip()
    ]
    
    BLACKLIST_SENDERS = [
        term.strip().lower()
        for term in os.getenv("BLACKLIST_SENDERS", "glassdoor,indeed,aliexpress,newsletter,noreply@,no-reply@").split(",")
        if term.strip()
    ]

    @classmethod
    def save_to_env_file(cls, updates: dict):
        """Helper function to update settings inside the local AppData .env file."""
        env_path = ENV_PATH
        current_env = {}
        
        # Read existing variables
        if os.path.exists(env_path):
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    if "=" in line and not line.strip().startswith("#"):
                        key, val = line.strip().split("=", 1)
                        current_env[key.strip()] = val.strip()

        # Update with new values
        for key, val in updates.items():
            current_env[key] = str(val)

        # Write back to file cleanly
        with open(env_path, "w", encoding="utf-8") as f:
            f.write("# Generated and updated dynamically by IMAP Inbox Helper Dashboard\n")
            for key, val in current_env.items():
                f.write(f"{key}={val}\n")

        # Reload updated environment variables
        load_dotenv(ENV_PATH, override=True)
        # Refresh current config fields
        cls.IMAP_HOST = os.getenv("IMAP_HOST", cls.IMAP_HOST)
        cls.IMAP_PORT = int(os.getenv("IMAP_PORT", cls.IMAP_PORT))
        cls.IMAP_SSL = os.getenv("IMAP_SSL", str(cls.IMAP_SSL)).lower() in ("true", "1", "yes")
        cls.IMAP_USER = os.getenv("IMAP_USER", cls.IMAP_USER)
        cls.IMAP_PASSWORD = os.getenv("IMAP_PASSWORD", cls.IMAP_PASSWORD)
        cls.MONITOR_FOLDER = os.getenv("MONITOR_FOLDER", cls.MONITOR_FOLDER)
        cls.POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", cls.POLL_INTERVAL))
        cls.IMPORTANCE_THRESHOLD = int(os.getenv("IMPORTANCE_THRESHOLD", cls.IMPORTANCE_THRESHOLD))
        cls.WHITELIST_SENDERS = [
            email.strip().lower()
            for email in os.getenv("WHITELIST_SENDERS", "").split(",")
            if email.strip()
        ]
        cls.BLACKLIST_SENDERS = [
            term.strip().lower()
            for term in os.getenv("BLACKLIST_SENDERS", "").split(",")
            if term.strip()
        ]
