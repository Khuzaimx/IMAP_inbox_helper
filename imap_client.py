import ssl
import email
from email.header import decode_header
from datetime import datetime
import time
from imapclient import IMAPClient
from config import Config
from db import log_event, insert_email
from classifier import analyze_email

def decode_mime_header(header_value: str) -> str:
    """Decodes MIME encoded headers safely into standard unicode strings."""
    if not header_value:
        return ""
    try:
        decoded_parts = decode_header(header_value)
        header_text = []
        for text, charset in decoded_parts:
            if isinstance(text, bytes):
                header_text.append(text.decode(charset or 'utf-8', errors='replace'))
            else:
                header_text.append(text)
        return "".join(header_text)
    except Exception as e:
        return str(header_value)

def extract_email_body(msg) -> str:
    """Extracts a plain text snippet or cleaned HTML snippet from an email message structure."""
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get("Content-Disposition"))
            
            if content_type == "text/plain" and "attachment" not in content_disposition:
                try:
                    payload = part.get_payload(decode=True)
                    charset = part.get_content_charset() or "utf-8"
                    body += payload.decode(charset, errors="replace")
                except Exception:
                    pass
            elif content_type == "text/html" and not body and "attachment" not in content_disposition:
                # Fallback to HTML if plain text isn't parsed yet
                try:
                    payload = part.get_payload(decode=True)
                    charset = part.get_content_charset() or "utf-8"
                    body += payload.decode(charset, errors="replace")
                except Exception:
                    pass
    else:
        try:
            payload = msg.get_payload(decode=True)
            charset = msg.get_content_charset() or "utf-8"
            body = payload.decode(charset, errors="replace")
        except Exception:
            pass
            
    # Simple HTML tags removal to get a clean text body
    if "<html" in body.lower() or "<div" in body.lower():
        body = re_strip_html(body)
        
    return body.strip()

def re_strip_html(html_text: str) -> str:
    """Basic regular expression to strip out HTML markup tags for a text snippet."""
    import re
    # Remove script and style elements
    text = re.sub(r'<script[^>]*?>.*?</script>', '', html_text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<style[^>]*?>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', ' ', text)
    # Normalize whitespaces
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

class IMAPInboxManager:
    def __init__(self):
        self.client = None
        self.is_connected = False

    def connect(self) -> bool:
        """Establishes an SSL connection to the IMAP server and logs in."""
        if not Config.IMAP_USER or not Config.IMAP_PASSWORD:
            log_event("WARNING", "IMAP credentials are not fully configured. Please configure them in settings.")
            return False
            
        try:
            log_event("IMAP", f"Connecting to IMAP server {Config.IMAP_HOST}:{Config.IMAP_PORT}...")
            
            # Configure modern secure SSL context
            context = ssl.create_default_context()
            self.client = IMAPClient(Config.IMAP_HOST, port=Config.IMAP_PORT, ssl=Config.IMAP_SSL, ssl_context=context)
            
            log_event("IMAP", "Logging in...")
            self.client.login(Config.IMAP_USER, Config.IMAP_PASSWORD)
            self.is_connected = True
            log_event("IMAP", "IMAP Login successful.")
            return True
        except Exception as e:
            self.is_connected = False
            log_event("ERROR", f"Failed to connect to IMAP server: {e}")
            return False

    def disconnect(self):
        """Safely closes the IMAP session."""
        if self.client:
            try:
                self.client.logout()
                log_event("IMAP", "Successfully logged out of IMAP.")
            except Exception:
                pass
        self.client = None
        self.is_connected = False

    def fetch_recent_emails(self, limit: int = 15) -> list:
        """
        Fetches the latest N emails from the configured folder, analyzes them, 
        and stores them in the local database.
        """
        if not self.is_connected and not self.connect():
            return []
            
        try:
            self.client.select_folder(Config.MONITOR_FOLDER)
            # Find all messages in folder
            messages = self.client.search(["ALL"])
            if not messages:
                log_event("IMAP", "No emails found in folder.")
                return []
                
            # Get latest limit messages
            recent_ids = messages[-limit:]
            log_event("IMAP", f"Fetching headers and body for {len(recent_ids)} latest emails...")
            
            fetched_emails = []
            
            # Fetch envelope, body data, and flags
            response = self.client.fetch(recent_ids, ["RFC822", "FLAGS"])
            for msg_id, data in response.items():
                try:
                    raw_email = data[b"RFC822"]
                    flags = data[b"FLAGS"]
                    is_read = b"\\Seen" in flags
                    
                    # Parse bytes using standard email parser
                    msg = email.message_from_bytes(raw_email)
                    
                    # Decode headers
                    subject = decode_mime_header(msg.get("Subject", ""))
                    sender = decode_mime_header(msg.get("From", ""))
                    to_field = decode_mime_header(msg.get("To", ""))
                    msg_id_header = msg.get("Message-ID", f"local-{hash(subject + sender + str(msg_id))}")
                    date_header = msg.get("Date", "")
                    
                    # Extract body content
                    body = extract_email_body(msg)
                    snippet = body[:400] + ("..." if len(body) > 400 else "")
                    
                    # Convert headers dictionary to lower keys for classifier checks
                    headers_dict = {}
                    for k, v in msg.items():
                        headers_dict[k.lower()] = v
                    # Ensure explicitly decoded fields are updated
                    headers_dict["subject"] = subject
                    headers_dict["from"] = sender
                    headers_dict["to"] = to_field
                    
                    # Run classifier
                    classification = analyze_email(headers_dict, body)
                    
                    email_item = {
                        "message_id": msg_id_header,
                        "subject": subject,
                        "sender": sender,
                        "date_sent": date_header,
                        "body_snippet": snippet,
                        "importance_score": classification["score"],
                        "is_important": classification["is_important"],
                        "classification_reason": classification["classification_reason"],
                        "is_read": is_read
                    }
                    
                    # Insert to local database
                    is_new = insert_email(email_item)
                    if is_new:
                        log_event("IMAP", f"Indexed new email: '{subject}' [Score: {classification['score']}]")
                        
                    fetched_emails.append(email_item)
                except Exception as e:
                    log_event("ERROR", f"Error parsing individual email {msg_id}: {e}")
                    
            return fetched_emails
        except Exception as e:
            log_event("ERROR", f"Failed to fetch emails: {e}")
            self.is_connected = False
            return []

    def perform_quick_action(self, message_id: str, action: str) -> bool:
        """Executes an action directly on the remote IMAP mailbox (e.g. Mark Read, Delete, Archive)."""
        if not self.is_connected and not self.connect():
            return False
            
        try:
            self.client.select_folder(Config.MONITOR_FOLDER)
            # Find the message UID using the Message-ID header
            # We search using header standard
            uids = self.client.search(["HEADER", "Message-ID", message_id])
            if not uids:
                log_event("WARNING", f"Email with Message-ID {message_id} not found on server.")
                return False
                
            uid = uids[0]
            if action == "mark_read":
                self.client.add_flags(uid, [b"\\Seen"])
                log_event("ACTION", f"Marked email {message_id} as read on IMAP server.")
                return True
            elif action == "delete":
                self.client.delete_messages(uid)
                self.client.expunge()
                log_event("ACTION", f"Deleted email {message_id} on IMAP server.")
                return True
            elif action == "archive":
                # Create Archive folder if not exists
                archive_folder = "Archive"
                if not self.client.folder_exists(archive_folder):
                    self.client.create_folder(archive_folder)
                self.client.move(uid, archive_folder)
                log_event("ACTION", f"Moved email {message_id} to Archive folder.")
                return True
                
            return False
        except Exception as e:
            log_event("ERROR", f"Failed to perform action '{action}' on server: {e}")
            self.is_connected = False
            return False
