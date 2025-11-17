
import os
from pathlib import Path
import pandas as pd
import streamlit as st
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from typing import Optional, List, Dict

# Rest of the gmail_reader code...

# imports from project modules (handle missing gracefully)
try:
    from src.classifier import SpamDetectionClassifier, load_default_model, predictMessage
except Exception:
    SpamDetectionClassifier = None
    load_default_model = None
    predictMessage = None

import importlib

try:
    # try importing as a project module first (e.g., src.gmail_reader), then fall back to top-level gmail_reader
    try:
        gmail_reader = importlib.import_module("src.gmail_reader")
    except Exception:
        gmail_reader = importlib.import_module("gmail_reader")
    _gmail_available = True
except Exception:
    gmail_reader = None
    _gmail_available = False

st.set_page_config(page_title="Email Spam Detector", page_icon="✉️", layout="centered")

# small CSS
st.markdown("<style>.main .block-container{padding-top:1.5rem}.stButton>button{width:100%}</style>", unsafe_allow_html=True)

st.title("✉️ Email Spam Detector")
st.markdown("Upload CSV (columns: `text`, `spam`) or use default `emails.csv`. Use Gmail integration to classify inbox messages.")

# session-state keys
if "classifier" not in st.session_state:
    st.session_state.classifier = None
if "default_model_loaded" not in st.session_state:
    st.session_state.default_model_loaded = False
if "uploaded_file_name" not in st.session_state:
    st.session_state.uploaded_file_name = None
if "authenticated_email" not in st.session_state:
    st.session_state.authenticated_email = None

# Sidebar upload
with st.sidebar:
    st.header("📊 Dataset")
    uploaded_file = st.file_uploader("Upload CSV (text, spam)", type="csv")

# Train on uploaded file once (store in session_state)
if uploaded_file is not None:
    try:
        # avoid retraining if same file
        if st.session_state.uploaded_file_name != getattr(uploaded_file, "name", None):
            df = pd.read_csv(uploaded_file)
            if "text" not in df.columns or "spam" not in df.columns:
                st.sidebar.error("CSV must contain 'text' and 'spam' columns")
            else:
                st.session_state.classifier = SpamDetectionClassifier(df) if SpamDetectionClassifier else None
                st.session_state.uploaded_file_name = getattr(uploaded_file, "name", None)
                st.sidebar.success("Model trained on uploaded dataset")
                st.sidebar.markdown(f"- Total: {len(df)}  \n- Spam: {int(df['spam'].sum())}")
                st.dataframe(df.head())
    except Exception as e:
        st.sidebar.error(f"Failed to load/train: {e}")

# If no uploaded model, try loading default once
elif not st.session_state.default_model_loaded:
    try:
        if load_default_model and load_default_model("emails.csv"):
            st.session_state.default_model_loaded = True
            st.sidebar.success("Using default model (emails.csv)")
        else:
            st.sidebar.info("No default model found. Upload CSV to train model.")
    except Exception as e:
        st.sidebar.error(f"Default model load error: {e}")
        st.session_state.default_model_loaded = False

st.markdown("---")
tab1, tab2 = st.tabs(["📝 Single Message", "📧 Gmail Inbox"])

with tab1:
    st.subheader("Analyze a single message")
    user_message = st.text_area("Message text", height=180)

    if st.button("Analyze Message"):
        if not user_message.strip():
            st.error("Please enter a message.")
        else:
            try:
                if st.session_state.classifier is not None:
                    label = st.session_state.classifier.predictMessage(user_message)
                    acc = st.session_state.classifier.get_accuracy()
                elif callable(predictMessage):
                    label = predictMessage(user_message)
                    acc = None
                else:
                    st.error("No model available. Upload dataset or provide emails.csv.")
                    st.stop()
                emoji = "🔴" if label == "Spam" else "🟢"
                st.success(f"{emoji} {label}")
                if acc is not None:
                    st.info(f"Model accuracy: {acc:.3f}")
            except Exception as e:
                st.error(f"Prediction failed: {e}")

with tab2:
    st.subheader("Classify Gmail messages")
    st.markdown(
        "Place `credentials.json` in project root for OAuth. First run will open browser for consent and create `token.json` automatically.\n\n"
        "**Important Setup Steps:**\n"
        "1. Configure OAuth consent screen in Google Cloud Console\n"
        "2. Add your email as a test user\n"
        "3. Add `http://localhost:8080/` to Authorized redirect URIs"
    )
    
    # Check if token exists and show current authentication status
    token_path = Path("token.json")
    if token_path.exists():
        try:
            from google.oauth2.credentials import Credentials
            from google.auth.transport.requests import Request
            creds = Credentials.from_authorized_user_file(str(token_path), ['https://www.googleapis.com/auth/gmail.readonly'])
            
            # Refresh token if expired
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                    # Save refreshed token
                    with open(token_path, "w") as token:
                        token.write(creds.to_json())
                except:
                    pass
            
            if creds and creds.valid:
                # Get user info (cache in session state to avoid repeated API calls)
                if st.session_state.authenticated_email is None:
                    try:
                        from googleapiclient.discovery import build
                        service = build('gmail', 'v1', credentials=creds)
                        profile = service.users().getProfile(userId='me').execute()
                        st.session_state.authenticated_email = profile.get('emailAddress', 'Unknown')
                    except:
                        st.session_state.authenticated_email = "Unknown"
                
                if st.session_state.authenticated_email and st.session_state.authenticated_email != "Unknown":
                    st.info(f"🔐 Currently authenticated as: **{st.session_state.authenticated_email}**")
                else:
                    st.info("🔐 Currently authenticated (email verification required)")
            else:
                st.warning("⚠️ Authentication token expired. Please re-authenticate.")
                st.session_state.authenticated_email = None
        except:
            st.warning("⚠️ Authentication token invalid. Please re-authenticate.")
            st.session_state.authenticated_email = None
        
        # Button to clear authentication
        if st.button("🔄 Switch Account / Clear Authentication", help="This will clear the current authentication and allow you to sign in with a different email"):
            try:
                token_path.unlink()
                st.session_state.authenticated_email = None
                st.success("✅ Authentication cleared! Click 'Classify Gmail' to authenticate with a different email.")
                st.rerun()
            except Exception as e:
                st.error(f"Failed to clear authentication: {e}")
    else:
        st.info("ℹ️ No authentication found. Click 'Classify Gmail' to authenticate.")
        st.session_state.authenticated_email = None
    
    query = st.text_input("Gmail query", value="in:inbox")
    max_messages = st.number_input("Max messages", min_value=1, max_value=500, value=50)

    if st.button("Classify Gmail"):
        if not _gmail_available:
            st.error("gmail_reader not available. Ensure gmail_reader.py is present and imports succeed.")
        else:
            # Check for credentials.json using the helper function from gmail_reader
            creds_file = None
            if hasattr(gmail_reader, 'find_credentials_file'):
                creds_file = gmail_reader.find_credentials_file()
            else:
                # Fallback: check common locations
                current_dir = Path.cwd()
                if (current_dir / "credentials.json").exists():
                    creds_file = str(current_dir / "credentials.json")
                elif (current_dir.parent / "credentials.json").exists():
                    creds_file = str(current_dir.parent / "credentials.json")
            
            if not creds_file:
                st.error(
                    "❌ **credentials.json missing**\n\n"
                    "To use Gmail integration:\n"
                    "1. Go to [Google Cloud Console](https://console.cloud.google.com/)\n"
                    "2. Create a project (or select existing)\n"
                    "3. Enable Gmail API\n"
                    "4. Configure OAuth consent screen:\n"
                    "   - Go to APIs & Services → OAuth consent screen\n"
                    "   - Select 'External' user type\n"
                    "   - Fill in app details (name, email)\n"
                    "   - Add scope: https://www.googleapis.com/auth/gmail.readonly\n"
                    "   - Add your email as a test user\n"
                    "5. Create OAuth 2.0 credentials (Desktop app)\n"
                    "6. **IMPORTANT**: Add `http://localhost:8080/` to Authorized redirect URIs\n"
                    "7. Download credentials.json\n"
                    "8. Place it in the `spam-detection-streamlit` directory"
                )
            else:
                try:
                    # Clear cached email to fetch fresh authentication info after classification
                    with st.spinner("Authenticating and classifying..."):
                        gmail_reader.classify_gmail_messages(save_csv=True, query=query or None, max_messages=int(max_messages))
                    # Clear cached email so it refreshes on next page load
                    st.session_state.authenticated_email = None
                    out = Path("gmail_classification_results.csv")
                    if out.exists():
                        df_out = pd.read_csv(out)
                        st.success(f"Classified {len(df_out)} messages")
                        st.dataframe(df_out.head())
                        st.download_button("Download results", df_out.to_csv(index=False).encode("utf-8"), "gmail_classification_results.csv")
                    else:
                        st.warning("No results file produced.")
                except Exception as e:
                    error_msg = str(e)
                    # Format error message for better readability
                    if "Address already in use" in error_msg or "address already in use" in error_msg.lower():
                        st.error(
                            f"❌ **Port Conflict Error**\n\n"
                            f"{error_msg}\n\n"
                            f"**Quick Fix:**\n"
                            f"1. Free up port 8080: `lsof -ti:8080 | xargs kill -9`\n"
                            f"2. Or wait a few seconds and try again\n"
                            f"3. The app will automatically try alternative ports if available"
                        )
                    elif "redirect_uri" in error_msg.lower():
                        st.error(f"❌ **OAuth Configuration Error**\n\n{error_msg}")
                    elif "access_denied" in error_msg.lower() or "verification process" in error_msg.lower() or "test user" in error_msg.lower():
                        st.error(f"❌ **OAuth Consent Screen Configuration Error**\n\n{error_msg}")
                    else:
                        st.error(f"❌ **Gmail classification failed**\n\n{error_msg}")
                    # Also show the full error in an expander for debugging
                    with st.expander("🔍 Error Details"):
                        st.code(error_msg)

st.markdown("---")
st.markdown("<div style='text-align:center'>Presented by  Gyan </div>", unsafe_allow_html=True)