import os
import base64
from email import utils as email_utils

try:
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
except ImportError:
    Credentials = None
    InstalledAppFlow = None
    Request = None
    build = None
    HttpError = Exception

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
TOKEN_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "token.json")
CREDENTIALS_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "credentials.json")


def get_auth_url() -> str:
    """Return instructions text for manual OAuth setup."""
    return (
        "1. Go to https://console.cloud.google.com/apis/credentials\n"
        "2. Create a project if you haven't already\n"
        "3. Enable the Gmail API\n"
        "4. Create OAuth 2.0 Client ID (Application type: Desktop app)\n"
        "5. Download the JSON file and save it as `credentials.json` in this project root\n"
        "6. Then click 'Start Auth' below"
    )


def authenticate_gmail() -> Credentials:
    """Run OAuth flow and return Gmail credentials."""
    if not os.path.exists(CREDENTIALS_FILE):
        raise FileNotFoundError(
            f"credentials.json not found at {CREDENTIALS_FILE}. "
            "Download it from Google Cloud Console and place it in the project root."
        )

    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=8080)

        with open(TOKEN_FILE, "w") as token:
            token.write(creds.to_json())

    return creds


def get_gmail_service():
    """Get an authenticated Gmail API service."""
    creds = authenticate_gmail()
    return build("gmail", "v1", credentials=creds)


def _decode_snippet(snippet: str) -> str:
    """Clean up email snippet."""
    return snippet[:200] if snippet else ""


def fetch_unread_emails(service, limit: int = 10) -> list:
    """Fetch the most recent unread emails."""
    try:
        results = service.users().messages().list(
            userId="me",
            q="is:unread",
            maxResults=limit,
        ).execute()

        messages = results.get("messages", [])
        if not messages:
            return []

        emails = []
        for msg in messages:
            msg_data = service.users().messages().get(
                userId="me",
                id=msg["id"],
                format="metadata",
                metadataHeaders=["From", "Subject", "Date"],
            ).execute()

            headers = msg_data.get("payload", {}).get("headers", [])
            from_addr = next((h["value"] for h in headers if h["name"] == "From"), "Unknown")
            subject = next((h["value"] for h in headers if h["name"] == "Subject"), "(No Subject)")
            date_str = next((h["value"] for h in headers if h["name"] == "Date"), "")
            snippet = msg_data.get("snippet", "")

            emails.append({
                "id": msg["id"],
                "from": from_addr,
                "subject": subject,
                "date": date_str,
                "snippet": _decode_snippet(snippet),
            })

        return emails
    except HttpError as error:
        raise RuntimeError(f"Gmail API error: {error}")


def mark_as_read(service, message_id: str):
    """Mark a specific email as read."""
    try:
        service.users().messages().modify(
            userId="me",
            id=message_id,
            body={"removeLabelIds": ["UNREAD"]},
        ).execute()
    except HttpError as error:
        raise RuntimeError(f"Gmail API error: {error}")
