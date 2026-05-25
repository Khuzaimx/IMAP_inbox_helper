import urllib.request
import urllib.parse
import json
import webbrowser
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import db

# Global OAuth Callback state
oauth_result = {
    "code": None,
    "error": None,
    "server": None
}

class OAuthCallbackHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Silence console log spam from local HTTP requests
        return

    def do_GET(self):
        query = urllib.parse.urlparse(self.path).query
        params = urllib.parse.parse_qs(query)
        
        code = params.get("code", [None])[0]
        error = params.get("error", [None])[0]
        
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        
        if code:
            oauth_result["code"] = code
            html = """
            <!DOCTYPE html>
            <html>
            <head>
                <title>Success</title>
                <style>
                    body { background: #09090b; color: #fafafa; font-family: sans-serif; text-align: center; padding-top: 50px; }
                    .card { border: 1px solid #27272a; display: inline-block; padding: 24px; border-radius: 8px; background: #161619; }
                    h2 { color: #10b981; }
                </style>
            </head>
            <body>
                <div class="card">
                    <h2>Authentication Successful</h2>
                    <p>Google OAuth integration approved. You can close this window now.</p>
                </div>
            </body>
            </html>
            """
            self.wfile.write(html.encode("utf-8"))
        else:
            oauth_result["error"] = error or "Unknown authorization failure"
            html = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>Error</title>
                <style>
                    body {{ background: #09090b; color: #fafafa; font-family: sans-serif; text-align: center; padding-top: 50px; }}
                    .card {{ border: 1px solid #ef4444; display: inline-block; padding: 24px; border-radius: 8px; background: #161619; }}
                    h2 {{ color: #ef4444; }}
                </style>
            </head>
            <body>
                <div class="card">
                    <h2>Authentication Failed</h2>
                    <p>Error: {error or 'Unknown authorization failure'}</p>
                </div>
            </body>
            </html>
            """
            self.wfile.write(html.encode("utf-8"))
            
        # Spawn short thread to shut down the server after responding
        threading.Thread(target=self.server.shutdown, daemon=True).start()

def run_local_oauth_listener(port=8080):
    """Spins up a temporary local HTTP server to receive the Google OAuth callback code."""
    oauth_result["code"] = None
    oauth_result["error"] = None
    
    server = HTTPServer(("localhost", port), OAuthCallbackHandler)
    oauth_result["server"] = server
    
    # Run server blocking loop (shutdown() will stop it)
    server.serve_forever()
    server.server_close()

def run_oauth_flow(client_id: str, client_secret: str) -> dict:
    """
    Orchestrates the entire Google Sign-In loop:
    Spawns background server, opens browser, performs token exchange and returns tokens.
    """
    redirect_uri = "http://localhost:8080/"
    scope = "https://mail.google.com/"
    
    # Reset states
    oauth_result["code"] = None
    oauth_result["error"] = None
    
    # Start callback listener thread
    listener_thread = threading.Thread(target=run_local_oauth_listener, args=(8080,), daemon=True)
    listener_thread.start()
    
    # Generate Google OAuth login URL
    # prompt=consent and access_type=offline guarantees a Refresh Token is returned
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": scope,
        "access_type": "offline",
        "prompt": "consent"
    }
    auth_url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode(params)
    
    db.log_event("OAUTH", "Opening Google sign-in page in system browser...")
    webbrowser.open(auth_url)
    
    # Wait for listener thread to finish (max 60 seconds)
    listener_thread.join(timeout=60)
    
    # Terminate server if it didn't shut down
    if oauth_result["server"]:
        try:
            oauth_result["server"].shutdown()
        except Exception:
            pass
            
    if oauth_result["error"]:
        raise Exception(oauth_result["error"])
        
    code = oauth_result["code"]
    if not code:
        raise Exception("Authorization timed out after 60 seconds.")
        
    db.log_event("OAUTH", "Exchanging authorization code for OAuth tokens...")
    
    # Exchange code for tokens
    token_url = "https://oauth2.googleapis.com/token"
    data = urllib.parse.urlencode({
        "code": code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code"
    }).encode("utf-8")
    
    req = urllib.request.Request(token_url, data=data, headers={"Content-Type": "application/x-www-form-urlencoded"})
    
    with urllib.request.urlopen(req) as response:
        res_data = json.loads(response.read().decode("utf-8"))
        
    return res_data

def refresh_access_token(client_id: str, client_secret: str, refresh_token: str) -> str:
    """Uses a stored Refresh Token to request a fresh, temporary Access Token from Google."""
    token_url = "https://oauth2.googleapis.com/token"
    data = urllib.parse.urlencode({
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token"
    }).encode("utf-8")
    
    req = urllib.request.Request(token_url, data=data, headers={"Content-Type": "application/x-www-form-urlencoded"})
    
    with urllib.request.urlopen(req) as response:
        res_data = json.loads(response.read().decode("utf-8"))
        
    return res_data["access_token"]
