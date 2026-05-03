"""
Connect Gmail to project classifier with improved port handling.
Requires:
 - credentials.json in project root
 - python packages: google-api-python-client google-auth-httplib2 google-auth-oauthlib pandas scikit-learn
"""

import os
import socket
import time
from pathlib import Path
from typing import Optional
import pandas as pd
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

# Define the scopes
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']
TOKEN_FILE = "token.json"
CREDENTIALS_FILE = "credentials.json"

def find_credentials_file():
    """Find credentials.json in current directory or parent directories."""
    current = Path.cwd()
    # Check current directory
    if (current / CREDENTIALS_FILE).exists():
        return str(current / CREDENTIALS_FILE)
    # Check parent directory
    if (current.parent / CREDENTIALS_FILE).exists():
        return str(current.parent / CREDENTIALS_FILE)
    # Check spam-detection-streamlit directory if we're in a subdirectory
    streamlit_dir = current
    while streamlit_dir != streamlit_dir.parent:
        if streamlit_dir.name == "spam-detection-streamlit" and (streamlit_dir / CREDENTIALS_FILE).exists():
            return str(streamlit_dir / CREDENTIALS_FILE)
        streamlit_dir = streamlit_dir.parent
    return None

def is_port_available(port: int) -> bool:
    """Check if a port is available."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(('localhost', port))
            return True
        except OSError:
            return False

def kill_process_on_port(port: int) -> bool:
    """Try to kill the process using the specified port."""
    try:
        import platform
        import subprocess
        
        system = platform.system()
        if system == "Darwin" or system == "Linux":
            # macOS or Linux
            subprocess.run(f"lsof -ti:{port} | xargs kill -9", shell=True, check=False)
        elif system == "Windows":
            # Windows
            subprocess.run(f"for /f \"tokens=5\" %a in ('netstat -aon ^| find \":{port}\" ^| find \"LISTENING\"') do taskkill /F /PID %a", shell=True, check=False)
        
        # Wait a moment for the port to be freed
        time.sleep(1)
        return is_port_available(port)
    except Exception:
        return False

def find_available_port(start_port: int = 8080, max_attempts: int = 10, try_kill: bool = True) -> int:
    """Find an available port starting from start_port."""
    # First, try the preferred port
    if is_port_available(start_port):
        return start_port
    
    # Try to kill process on preferred port if requested
    if try_kill:
        print(f"⚠️  Port {start_port} is in use. Attempting to free it...")
        if kill_process_on_port(start_port):
            print(f"✅ Port {start_port} freed successfully!")
            return start_port
        else:
            print(f"⚠️  Could not free port {start_port}. Trying alternative ports...")
    
    # Try alternative ports
    for port in range(start_port + 1, start_port + max_attempts):
        if is_port_available(port):
            return port
    
    raise RuntimeError(
        f"❌ Could not find an available port in range {start_port}-{start_port + max_attempts - 1}.\n\n"
        f"To fix this:\n"
        f"1. Free up port {start_port} manually:\n"
        f"   - On macOS/Linux: lsof -ti:{start_port} | xargs kill -9\n"
        f"   - On Windows: Find and stop the process using port {start_port}\n"
        f"2. Or add multiple redirect URIs to Google Cloud Console:\n"
        f"   - http://localhost:{start_port}/\n"
        f"   - http://localhost:{start_port + 1}/\n"
        f"   - http://localhost:{start_port + 2}/\n"
        f"   etc."
    )

def gmail_authenticate():
    """Authenticate and return the Gmail service."""
    creds = None
    # Check if token file exists (in current directory)
    token_path = Path(TOKEN_FILE)
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
    
    # If there are no (valid) credentials available, let the user log in
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception:
                # Refresh failed, need to re-authenticate
                creds = None
        
        if not creds or not creds.valid:
            creds_file = find_credentials_file()
            if not creds_file:
                raise FileNotFoundError(
                    f"{CREDENTIALS_FILE} not found. Please download it from Google Cloud Console "
                    f"and place it in the project root directory."
                )
            flow = InstalledAppFlow.from_client_secrets_file(creds_file, SCOPES)
            
            # Try to find an available port (with automatic port 8080 cleanup)
            try:
                port = find_available_port(8080, max_attempts=10, try_kill=True)
                if port != 8080:
                    print(f"⚠️  Using port {port} instead of 8080.")
                    print(f"   Make sure http://localhost:{port}/ is added to Authorized redirect URIs in Google Cloud Console!")
            except RuntimeError as e:
                raise RuntimeError(str(e))
            
            try:
                creds = flow.run_local_server(port=port, open_browser=True)
            except OSError as e:
                error_msg = str(e)
                if "Address already in use" in error_msg or "address already in use" in error_msg.lower():
                    raise RuntimeError(
                        f"❌ Port {port} became unavailable during authentication (race condition).\n\n"
                        f"To fix this:\n"
                        f"1. Wait a few seconds and try again\n"
                        f"2. Or manually free up port {port}\n"
                        f"3. Make sure http://localhost:{port}/ is added to Authorized redirect URIs"
                    )
                raise
            except Exception as e:
                error_msg = str(e)
                error_lower = error_msg.lower()
                
                # Handle redirect URI mismatch
                if "redirect_uri_mismatch" in error_lower or ("redirect_uri" in error_lower and "mismatch" in error_lower):
                    raise RuntimeError(
                        f"❌ Redirect URI Mismatch Error!\n\n"
                        f"To fix this:\n"
                        f"1. Go to Google Cloud Console → APIs & Services → Credentials\n"
                        f"2. Click on your OAuth 2.0 Client ID\n"
                        f"3. Under 'Authorized redirect URIs', add: http://localhost:{port}/\n"
                        f"4. Click Save\n"
                        f"5. Wait a few seconds for changes to propagate\n"
                        f"6. Try again\n\n"
                        f"Original error: {error_msg}"
                    )
                
                # Handle access denied / app not verified
                if "access_denied" in error_lower or "403" in error_msg or "verification process" in error_lower or "test user" in error_lower:
                    raise RuntimeError(
                        "❌ Access Denied: App Not Verified / Test User Required\n\n"
                        "Your Gmail app is in 'Testing' mode and requires test users to be added.\n\n"
                        "**To fix this, complete BOTH steps:**\n\n"
                        "**STEP 1: Configure OAuth Consent Screen**\n"
                        "1. Go to Google Cloud Console → APIs & Services → OAuth consent screen\n"
                        "2. Under 'User Type', select 'External' (or 'Internal' if using Google Workspace)\n"
                        "3. Fill in the required app information\n"
                        "4. Add scopes: https://www.googleapis.com/auth/gmail.readonly\n"
                        "5. Add test users (CRITICAL):\n"
                        "   - Click 'Add Users'\n"
                        "   - Add your email address\n"
                        "   - Click 'Add'\n\n"
                        "**STEP 2: Add Redirect URI**\n"
                        "1. Go to APIs & Services → Credentials\n"
                        "2. Click on your OAuth 2.0 Client ID\n"
                        "3. Under 'Authorized redirect URIs', add:\n"
                        f"   - http://localhost:8080/\n"
                        f"   - http://localhost:{port}/\n"
                        "4. Click 'Save'\n"
                        "5. Wait 1-2 minutes for changes to propagate\n"
                        "6. Try again\n\n"
                        f"Original error: {error_msg}"
                    )
                
                raise
        
        # Save the credentials for the next run (in current directory)
        with open(token_path, "w") as token:
            token.write(creds.to_json())
    
    return build('gmail', 'v1', credentials=creds)

def list_message_ids(service, query=None, max_results=50):
    """List message IDs based on a query."""
    try:
        response = service.users().messages().list(userId='me', q=query, maxResults=max_results).execute()
        messages = response.get('messages', [])
        return [msg['id'] for msg in messages]
    except Exception as e:
        raise RuntimeError(f"Failed to list messages: {e}")

def get_message(service, msg_id):
    """Get a message by ID."""
    try:
        return service.users().messages().get(userId='me', id=msg_id, format='full').execute()
    except Exception as e:
        raise RuntimeError(f"Failed to get message {msg_id}: {e}")

def classify_gmail_messages(save_csv: bool = True, query: Optional[str] = None, max_messages: int = 50):
    """Classify Gmail messages and optionally save results to CSV."""
    if not find_credentials_file():
        raise FileNotFoundError(
            f"{CREDENTIALS_FILE} not found. Please download it from Google Cloud Console "
            f"and place it in the project root directory."
        )
    
    # Import predictMessage function
    try:
        from src.classifier import predictMessage
    except ImportError:
        try:
            from classifier import predictMessage
        except ImportError:
            raise ImportError("Could not import predictMessage from classifier module")
    
    try:
        svc = gmail_authenticate()
    except Exception as e:
        raise RuntimeError(f"Gmail authentication failed: {e}")

    ids = list_message_ids(svc, query=query, max_results=max_messages)
    if not ids:
        print("No messages found for the query.")
        return []

    results = []
    for msg_id in ids:
        try:
            m = get_message(svc, msg_id)
            text = (m.get('snippet') or '').strip()
            if not text:
                continue
            
            # Extract headers properly
            headers = m.get('payload', {}).get('headers', [])
            from_header = next((h['value'] for h in headers if h['name'].lower() == 'from'), 'Unknown')
            subject_header = next((h['value'] for h in headers if h['name'].lower() == 'subject'), 'No Subject')
            
            label = predictMessage(text)
            results.append({
                'id': m['id'],
                'from': from_header,
                'subject': subject_header,
                'label': label,
                'snippet': text[:200]
            })
            print(f"{from_header[:60]:60} | {subject_header[:60]:60} | {label}")
        except Exception as e:
            print(f"Error processing message {msg_id}: {str(e)}")
            continue

    if save_csv and results:
        try:
            out_path = "gmail_classification_results.csv"
            pd.DataFrame(results).to_csv(out_path, index=False)
            print(f"\nSaved results to {out_path}")
        except Exception as e:
            raise RuntimeError(f"Failed to save results to CSV: {e}")

    return results