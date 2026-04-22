import os
from datetime import datetime, timezone, timedelta

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

SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]
TOKEN_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "token_calendar.json")
CREDENTIALS_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "credentials.json")


def authenticate_calendar() -> "Credentials":
    if not os.path.exists(CREDENTIALS_FILE):
        raise FileNotFoundError(
            f"credentials.json not found at {CREDENTIALS_FILE}. "
            "Download from Google Cloud Console and place in project root."
        )

    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=8081)

        with open(TOKEN_FILE, "w") as token:
            token.write(creds.to_json())

    return creds


def get_calendar_service():
    creds = authenticate_calendar()
    return build("calendar", "v3", credentials=creds)


def fetch_todays_events(service) -> list:
    now = datetime.now(timezone.utc)
    start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_day = start_of_day + timedelta(days=1)

    try:
        result = service.events().list(
            calendarId="primary",
            timeMin=start_of_day.isoformat(),
            timeMax=end_of_day.isoformat(),
            singleEvents=True,
            orderBy="startTime",
        ).execute()
        return [_format_event(e) for e in result.get("items", [])]
    except HttpError as error:
        raise RuntimeError(f"Calendar API error: {error}")


def fetch_upcoming_events(service, days: int = 3) -> list:
    now = datetime.now(timezone.utc)
    end = now + timedelta(days=days)

    try:
        result = service.events().list(
            calendarId="primary",
            timeMin=now.isoformat(),
            timeMax=end.isoformat(),
            maxResults=20,
            singleEvents=True,
            orderBy="startTime",
        ).execute()
        return [_format_event(e) for e in result.get("items", [])]
    except HttpError as error:
        raise RuntimeError(f"Calendar API error: {error}")


def _format_event(event: dict) -> dict:
    start = event.get("start", {})
    end = event.get("end", {})
    start_dt = start.get("dateTime") or start.get("date", "")
    end_dt = end.get("dateTime") or end.get("date", "")
    all_day = "dateTime" not in start

    return {
        "id": event.get("id", ""),
        "title": event.get("summary", "(No title)"),
        "start": start_dt,
        "end": end_dt,
        "start_display": _fmt_time(start_dt, all_day),
        "end_display": _fmt_time(end_dt, all_day),
        "all_day": all_day,
        "location": event.get("location", ""),
        "description": (event.get("description") or "")[:200],
    }


def _fmt_time(dt_str: str, all_day: bool) -> str:
    if not dt_str:
        return ""
    if all_day:
        try:
            return datetime.strptime(dt_str, "%Y-%m-%d").strftime("%b %d")
        except ValueError:
            return dt_str
    try:
        dt = datetime.fromisoformat(dt_str)
        return dt.strftime("%I:%M %p").lstrip("0")
    except ValueError:
        return dt_str
