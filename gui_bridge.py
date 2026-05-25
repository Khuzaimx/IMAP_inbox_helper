import json
from config import Config
import db
from imap_client import IMAPInboxManager
from classifier import analyze_email

class GUIBridge:
    def __init__(self, app_state):
        self.app_state = app_state
        self.imap_manager = IMAPInboxManager()

    def get_emails(self, only_important: bool = False) -> str:
        """Fetches indexed emails from SQLite and returns them as a JSON string."""
        try:
            emails = db.get_emails(limit=100, only_important=only_important)
            return json.dumps({"success": True, "data": emails})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    def get_logs(self) -> str:
        """Fetches the latest runtime log entries as a JSON string."""
        try:
            logs = db.get_logs(limit=150)
            return json.dumps({"success": True, "data": logs})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    def perform_action(self, message_id: str, action: str) -> str:
        """Executes a mailbox action (e.g. mark read, archive, delete) on IMAP and SQLite DB."""
        try:
            db.log_event("ACTION", f"User requested '{action}' for email {message_id}")
            
            # Sync to remote server
            if self.imap_manager.connect():
                success = self.imap_manager.perform_quick_action(message_id, action)
                self.imap_manager.disconnect()
                
                if success:
                    # Update local database
                    if action == "mark_read":
                        db.update_read_status(message_id, is_read=True)
                    elif action == "delete":
                        # We can flag it locally, or remove it, or update it
                        # Let's mark it in DB or remove it
                        conn = db.get_connection()
                        cursor = conn.cursor()
                        cursor.execute("DELETE FROM emails WHERE message_id = ?", (message_id,))
                        conn.commit()
                        conn.close()
                    elif action == "archive":
                        conn = db.get_connection()
                        cursor = conn.cursor()
                        cursor.execute("DELETE FROM emails WHERE message_id = ?", (message_id,))
                        conn.commit()
                        conn.close()
                        
                    db.log_event("SUCCESS", f"Action '{action}' succeeded on server and local DB.")
                    return json.dumps({"success": True})
                else:
                    return json.dumps({"success": False, "error": "IMAP server action failed."})
            else:
                return json.dumps({"success": False, "error": "Could not connect to IMAP server."})
        except Exception as e:
            db.log_event("ERROR", f"Failed to perform action '{action}': {e}")
            return json.dumps({"success": False, "error": str(e)})

    def get_settings(self) -> str:
        """Returns the current configurations as a JSON string."""
        settings = {
            "IMAP_HOST": Config.IMAP_HOST,
            "IMAP_PORT": Config.IMAP_PORT,
            "IMAP_SSL": Config.IMAP_SSL,
            "IMAP_USER": Config.IMAP_USER,
            "IMAP_PASSWORD": Config.IMAP_PASSWORD,
            "MONITOR_FOLDER": Config.MONITOR_FOLDER,
            "POLL_INTERVAL": Config.POLL_INTERVAL,
            "IMPORTANCE_THRESHOLD": Config.IMPORTANCE_THRESHOLD,
            "WHITELIST_SENDERS": ", ".join(Config.WHITELIST_SENDERS),
            "BLACKLIST_SENDERS": ", ".join(Config.BLACKLIST_SENDERS)
        }
        return json.dumps({"success": True, "data": settings})

    def save_settings(self, settings_json: str) -> str:
        """Saves settings passed from JS to the local .env configuration file."""
        try:
            settings = json.loads(settings_json)
            updates = {
                "IMAP_HOST": settings.get("IMAP_HOST", "").strip(),
                "IMAP_PORT": int(settings.get("IMAP_PORT", 993)),
                "IMAP_SSL": "True" if settings.get("IMAP_SSL") else "False",
                "IMAP_USER": settings.get("IMAP_USER", "").strip(),
                "IMAP_PASSWORD": settings.get("IMAP_PASSWORD", "").strip(),
                "MONITOR_FOLDER": settings.get("MONITOR_FOLDER", "INBOX").strip(),
                "POLL_INTERVAL": int(settings.get("POLL_INTERVAL", 300)),
                "IMPORTANCE_THRESHOLD": int(settings.get("IMPORTANCE_THRESHOLD", 50)),
                # Format whitelists/blacklists back into comma-separated items
                "WHITELIST_SENDERS": ",".join([x.strip() for x in settings.get("WHITELIST_SENDERS", "").split(",") if x.strip()]),
                "BLACKLIST_SENDERS": ",".join([x.strip() for x in settings.get("BLACKLIST_SENDERS", "").split(",") if x.strip()])
            }
            
            Config.save_to_env_file(updates)
            db.log_event("CONFIG", "Configuration updated and reloaded from Dashboard.")
            return json.dumps({"success": True})
        except Exception as e:
            db.log_event("ERROR", f"Failed to save settings: {e}")
            return json.dumps({"success": False, "error": str(e)})

    def trigger_manual_sync(self) -> str:
        """Triggers an immediate background sync thread of the mailbox."""
        try:
            db.log_event("SYNC", "Manual synchronization triggered by user.")
            # Set the sync flag in our shared state
            self.app_state["trigger_sync"] = True
            return json.dumps({"success": True})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    def test_classifier(self, headers_json: str, body: str) -> str:
        """Simulates and runs the classifier locally on sample headers and body text."""
        try:
            headers = json.loads(headers_json)
            result = analyze_email(headers, body)
            return json.dumps({"success": True, "data": result})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    def clear_database(self) -> str:
        """Clears SQLite indexed emails and log history."""
        try:
            db.clear_all_data()
            return json.dumps({"success": True})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})
