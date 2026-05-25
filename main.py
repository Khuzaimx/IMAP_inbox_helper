import os
import sys
import threading
import time
import webview
from config import Config
import db
from imap_client import IMAPInboxManager
from gui_bridge import GUIBridge

# Set explicit AppUserModelID on Windows so the OS groups our taskbar process separately
if os.name == 'nt':
    try:
        import ctypes
        myappid = 'khuzaimx.imapinboxhelper.router.1.0'
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    except Exception:
        pass

# Global shared application state
app_state = {
    "running": True,
    "trigger_sync": False,
    "sync_in_progress": False
}

def imap_sync_worker(state):
    """
    Background worker thread that manages the IMAP email synchronization.
    Runs periodically or immediately when a manual sync is triggered.
    """
    db.log_event("SYSTEM", "Background IMAP sync thread started.")
    imap_manager = IMAPInboxManager()
    
    last_poll_time = 0
    
    while state["running"]:
        current_time = time.time()
        poll_interval = Config.POLL_INTERVAL
        
        # Determine if we should perform a sync
        should_sync = (
            state["trigger_sync"] or 
            (current_time - last_poll_time >= poll_interval)
        )
        
        if should_sync and not state["sync_in_progress"]:
            state["sync_in_progress"] = True
            state["trigger_sync"] = False  # Reset manual trigger
            
            db.log_event("SYNC", "Starting mail synchronization cycle...")
            
            try:
                # Fetch recent 20 emails, classify them and save to SQLite
                emails = imap_manager.fetch_recent_emails(limit=25)
                last_poll_time = time.time()
                db.log_event("SYNC", f"Mail synchronization completed. Checked {len(emails)} emails.")
            except Exception as e:
                db.log_event("ERROR", f"Error during background IMAP sync: {e}")
            finally:
                imap_manager.disconnect()
                state["sync_in_progress"] = False
                
        # Sleep for a short duration to remain responsive to state changes and limit CPU usage
        time.sleep(1)
        
    db.log_event("SYSTEM", "Background IMAP sync thread stopped.")

def on_closed():
    """Triggers clean shutdown of background threads when UI window is closed."""
    db.log_event("SYSTEM", "Desktop window closed. Cleaning up resources...")
    app_state["running"] = False

def main():
    db.log_event("SYSTEM", "Initializing Desktop IMAP Inbox Helper...")
    
    # Initialize DB (creates files/tables if missing)
    db.init_db()
    
    # Start the background IMAP worker thread
    worker_thread = threading.Thread(
        target=imap_sync_worker, 
        args=(app_state,), 
        daemon=True
    )
    worker_thread.start()
    
    # Expose the API bridge to the HTML UI
    bridge = GUIBridge(app_state)
    
    # Find absolute path of index.html UI
    base_dir = os.path.dirname(os.path.abspath(__file__))
    ui_file = os.path.join(base_dir, "ui", "index.html")
    
    # Fallback to create the UI folder structure if missing (will be populated next)
    os.makedirs(os.path.join(base_dir, "ui"), exist_ok=True)
    os.makedirs(os.path.join(base_dir, "ui", "css"), exist_ok=True)
    os.makedirs(os.path.join(base_dir, "ui", "js"), exist_ok=True)
    
    db.log_event("SYSTEM", f"Loading GUI from: {ui_file}")
    
    # Create the pywebview native desktop window
    window = webview.create_window(
        title="Intelligent Inbox Mail Router",
        url=ui_file,
        js_api=bridge,
        width=1150,
        height=760,
        min_size=(950, 650),
        background_color="#0b0f19"  # Matches CSS dark background for smooth loading
    )
    
    # Hook window close event to clean shutdown
    window.events.closed += on_closed
    
    # Start the GUI shell
    # On Windows, this runs the native Edge WebView2 loop
    webview.start(debug=False)

if __name__ == "__main__":
    main()
