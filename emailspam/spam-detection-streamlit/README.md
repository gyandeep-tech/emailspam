# Spam Detection Classifier

This project implements a spam detection classifier using a Naive Bayes algorithm. It is built with Python and utilizes Streamlit for the web application interface.

## Project Structure

```
spam-detection-streamlit
├── src
│   ├── classifier.py       # Implementation of the spam detection classifier
│   └── __init__.py         # Marks the src directory as a Python package
├── emails.csv              # Dataset containing email texts and labels (spam or ham)
├── app.py                  # Main entry point for the Streamlit application
├── requirements.txt         # Lists the dependencies required for the project
└── README.md               # Documentation for the project
```

## Setup Instructions

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd spam-detection-streamlit
   ```

2. **Create a virtual environment** (optional but recommended):
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows use `venv\Scripts\activate`
   ```

3. **Install the required packages**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Run the Streamlit application**:
   ```bash
   streamlit run app.py
   ```

## Usage

- Once the application is running, you can enter a message in the provided input box to check if it is classified as spam or ham.
- The results will be displayed on the web interface.
- You can also use Gmail integration to classify emails from your inbox (see Gmail Integration section below).

## Gmail Integration Setup

To use the Gmail integration feature:

1. **Go to Google Cloud Console**:
   - Visit [Google Cloud Console](https://console.cloud.google.com/)
   - Create a new project or select an existing one

2. **Enable Gmail API**:
   - Navigate to "APIs & Services" → "Library"
   - Search for "Gmail API" and enable it

3. **Configure OAuth Consent Screen** (REQUIRED):
   - Go to "APIs & Services" → "OAuth consent screen"
   - Select "External" as user type (or "Internal" if using Google Workspace)
   - Click "Create"
   - Fill in the required information:
     - **App name**: Gmail Reader App (or your preferred name)
     - **User support email**: Select your email address
     - **Developer contact information**: Enter your email address
   - Click "Save and Continue"
   - **Add Scopes**:
     - Click "Add or Remove Scopes"
     - Search for and add: `https://www.googleapis.com/auth/gmail.readonly`
     - Click "Update" then "Save and Continue"
   - **Add Test Users** (CRITICAL for Testing mode):
     - Click "Add Users"
     - Enter your email address (the one you'll use to sign in)
     - Click "Add"
     - Click "Save and Continue"
   - Review and click "Back to Dashboard"

4. **Create OAuth 2.0 Credentials**:
   - Go to "APIs & Services" → "Credentials"
   - Click "Create Credentials" → "OAuth client ID"
   - Choose "Desktop app" as the application type
   - Give it a name (e.g., "Gmail Reader App")
   - Click "Create"

5. **Configure Redirect URI** (IMPORTANT):
   - After creating the OAuth client, click on it to edit
   - Under "Authorized redirect URIs", click "Add URI"
   - Add the following URIs (add multiple to cover all scenarios):
     - `http://localhost:8080/` (primary port)
     - `http://localhost:8081/` (fallback if 8080 is busy)
     - `http://localhost:8082/` (additional fallback)
   - Click "Save"
   - **Note**: The app will automatically try alternative ports if 8080 is busy, so adding multiple ports ensures it works in all cases

6. **Download credentials.json**:
   - Click the download button (⬇️) next to your OAuth client
   - Save the file as `credentials.json`
   - Place it in the `spam-detection-streamlit` directory

7. **Run the app and authenticate**:
   - Start the Streamlit app
   - Go to the "Gmail Inbox" tab
   - Click "Classify Gmail"
   - A browser window will open for OAuth consent
   - After consent, `token.json` will be created automatically

**Troubleshooting**:
- **Error 403: access_denied**: Make sure you've added your email as a test user in the OAuth consent screen
- **redirect_uri_mismatch**: Ensure `http://localhost:8080/` is added to Authorized redirect URIs
- **Port already in use**: The app will automatically try alternative ports (8081, 8082, etc.)

## Dependencies

- Streamlit
- pandas
- scikit-learn
- google-api-python-client
- google-auth-httplib2
- google-auth-oauthlib

Make sure to check the `requirements.txt` file for the specific versions of the libraries used.