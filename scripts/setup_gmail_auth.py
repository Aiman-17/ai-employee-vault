"""
scripts/setup_gmail_auth.py — One-time Gmail OAuth2 authorisation helper.

Run this script once to authorise the Digital FTE Agent to read your Gmail:

    python scripts/setup_gmail_auth.py

A browser window will open. Log in and grant the requested permissions.
The token is saved to the path set in GMAIL_TOKEN_PATH (default:
credentials/gmail_token.json).

Prerequisites:
  1. Create a Google Cloud project and enable the Gmail API.
  2. Create OAuth2 "Desktop app" credentials and download as JSON.
  3. Save the JSON to the path set in GMAIL_CREDENTIALS_PATH (default:
     credentials/gmail_credentials.json).
  4. Run this script.

Security:
  - The token file is sensitive — NEVER commit it to git.
  - It is listed in .gitignore by default.
  - Rotate by deleting the token file and re-running this script.
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# OAuth2 scopes needed by GmailWatcher and email-mcp
SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",    # GmailWatcher — read + list
    "https://www.googleapis.com/auth/gmail.send",        # email-mcp — send emails
    "https://www.googleapis.com/auth/gmail.compose",     # email-mcp — create drafts
]

DEFAULT_CREDS = Path("credentials/gmail_credentials.json")
DEFAULT_TOKEN = Path("credentials/gmail_token.json")


def main() -> None:
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
    except ImportError:
        print(
            "ERROR: Required packages not installed.\n"
            "Run: pip install google-auth-oauthlib google-api-python-client"
        )
        sys.exit(1)

    creds_path = Path(os.getenv("GMAIL_CREDENTIALS_PATH", str(DEFAULT_CREDS)))
    token_path = Path(os.getenv("GMAIL_TOKEN_PATH", str(DEFAULT_TOKEN)))

    if not creds_path.exists():
        print(
            f"ERROR: Gmail credentials file not found at:\n  {creds_path}\n\n"
            "Steps to create it:\n"
            "  1. Go to https://console.cloud.google.com/\n"
            "  2. Create a project → Enable Gmail API\n"
            "  3. Credentials → Create → OAuth client ID → Desktop app\n"
            "  4. Download JSON → save to:\n"
            f"     {creds_path}\n"
            "  5. Re-run this script."
        )
        sys.exit(1)

    creds = None
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

    if creds and creds.valid:
        print(f"✅ Token already valid at: {token_path}")
        print("   Delete the token file and re-run to force re-authorisation.")
        return

    if creds and creds.expired and creds.refresh_token:
        print("Token expired — refreshing automatically…")
        creds.refresh(Request())
    else:
        print("Opening browser for Gmail authorisation…")
        flow = InstalledAppFlow.from_client_secrets_file(str(creds_path), SCOPES)
        creds = flow.run_local_server(port=0)

    # Ensure credentials directory exists
    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(creds.to_json(), encoding="utf-8")

    print(f"\n✅ Gmail authorised successfully!")
    print(f"   Token saved to: {token_path}")
    print(f"\n⚠️  Keep this file private — NEVER commit it to git.")
    print("   The GmailWatcher will now start monitoring your inbox.")


if __name__ == "__main__":
    main()
