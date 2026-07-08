from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextBrowser, QGroupBox, QScrollArea, QFrame,
)
from PyQt6.QtCore import Qt
import markdown as md_lib


def _render_md(text):
    body = md_lib.markdown(text or "", extensions=["tables", "fenced_code"])
    return f"""<html><head><style>
    body{{font-family:'Segoe UI',sans-serif;color:#EEF2FF;background:#070d1a;padding:14px;line-height:1.7;}}
    h1,h2,h3{{color:#c7d2fe;}}strong{{color:#a5b4fc;}}
    code{{background:#1e293b;padding:2px 6px;border-radius:3px;color:#22D3EE;font-size:12px;}}
    pre{{background:#0f1929;padding:10px;border-radius:6px;}}
    p{{margin:4px 0;}}
    </style></head><body>{body}</body></html>"""


def _format_weather(data):
    """Convert weather dict to a readable string for the QLabel."""
    if not data or isinstance(data, str):
        return data
    lines = [
        f"Temp: {data.get('temp_f', '?')}°F (feels like {data.get('feels_like_f', '?')}°F)",
        f"Condition: {data.get('description', 'N/A')}",
        f"Humidity: {data.get('humidity', '?')}%  |  Wind: {data.get('wind_mph', '?')} mph {data.get('wind_dir', '')}  |  UV: {data.get('uv_index', '?')}",
    ]
    return "\n".join(lines)


def _weather_html(data):
    if not data or isinstance(data, str):
        return f"<p style='color:#94a3b8'>{data or 'Weather unavailable'}</p>"

    def val(key, fallback="?"):
        value = data.get(key)
        return fallback if value in (None, "") else value

    forecast_cards = []
    for day in (data.get("forecast") or [])[:3]:
        hours = day.get("hourly") or [{}]
        hourly = hours[4] if len(hours) > 4 else hours[0]
        desc = hourly.get("weatherDesc", [{}])[0].get("value", "")
        forecast_cards.append(
            "<td style='padding:9px 10px;border:1px solid #1e293b;border-radius:8px;background:#0a1020'>"
            f"<div style='font-size:11px;color:#64748b;font-weight:700'>{day.get('date', '')}</div>"
            f"<div style='font-size:16px;color:#EEF2FF;font-weight:800'>{day.get('maxtempF', '?')} / {day.get('mintempF', '?')} F</div>"
            f"<div style='font-size:12px;color:#94a3b8'>{desc}</div>"
            "</td>"
        )

    forecast = ""
    if forecast_cards:
        forecast = (
            "<div style='margin-top:12px;color:#64748b;font-size:10px;font-weight:800;letter-spacing:1px'>FORECAST</div>"
            "<table cellspacing='6' cellpadding='0' style='width:100%;margin-left:-6px'><tr>"
            + "".join(forecast_cards)
            + "</tr></table>"
        )

    return f"""
    <html><body style='background:#070d1a;color:#EEF2FF;font-family:Segoe UI;padding:10px'>
      <div style='display:flex;align-items:flex-start;justify-content:space-between;gap:12px'>
        <div>
          <div style='font-size:34px;font-weight:900;line-height:1;color:#EEF2FF'>{val('temp_f')} F</div>
          <div style='font-size:13px;color:#94a3b8;margin-top:5px'>Feels like {val('feels_like_f')} F</div>
          <div style='font-size:14px;color:#c7d2fe;margin-top:8px;font-weight:700'>{val('description', 'N/A')}</div>
        </div>
        <div style='min-width:145px;background:#0a1020;border:1px solid #1e293b;border-radius:8px;padding:10px'>
          <div style='font-size:11px;color:#64748b'>Wind</div>
          <div style='font-size:18px;font-weight:800;color:#22D3EE'>{val('wind_mph')} mph {val('wind_dir', '')}</div>
          <div style='height:1px;background:#1e293b;margin:8px 0'></div>
          <div style='font-size:11px;color:#64748b'>Humidity</div>
          <div style='font-size:16px;font-weight:800;color:#EEF2FF'>{val('humidity')}%</div>
        </div>
      </div>
      <table cellspacing='6' cellpadding='0' style='width:100%;margin:12px 0 0 -6px'>
        <tr>
          <td style='padding:9px 10px;border:1px solid #1e293b;border-radius:8px;background:#0a1020'><div style='font-size:11px;color:#64748b'>Visibility</div><div style='font-size:16px;font-weight:800'>{val('visibility_mi')} mi</div></td>
          <td style='padding:9px 10px;border:1px solid #1e293b;border-radius:8px;background:#0a1020'><div style='font-size:11px;color:#64748b'>UV Index</div><div style='font-size:16px;font-weight:800'>{val('uv_index')}</div></td>
        </tr>
      </table>
      {forecast}
    </body></html>
    """


def _calendar_time_label(event):
    if event.get("all_day"):
        return f"All day - {event.get('start_display') or event.get('start', '')}"
    start = event.get("start_display") or event.get("start", "")
    end = event.get("end_display") or event.get("end", "")
    return f"{start} - {end}" if end else start


def _calendar_location(event):
    location = event.get("location")
    if not location:
        return ""
    return f"<span style='color:#64748b;font-size:11px'> | {location}</span>"


def _calendar_description(event):
    description = event.get("description")
    if not description:
        return ""
    return f"<div style='color:#94a3b8;font-size:12px;margin-top:4px'>{description}</div>"


class BriefingTab(QWidget):
    def __init__(self):
        super().__init__()
        self._weather_worker = None
        self._llm_worker = None
        self._emails = []
        self._setup_ui()

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(10)

        # Header
        header_row = QHBoxLayout()
        title = QLabel("Morning Briefing")
        title.setStyleSheet("font-size:18px;font-weight:700;color:#EEF2FF;")
        refresh_btn = QPushButton("Refresh All")
        refresh_btn.setObjectName("primary")
        refresh_btn.setFixedWidth(110)
        refresh_btn.clicked.connect(self._refresh_all)
        header_row.addWidget(title)
        header_row.addStretch()
        header_row.addWidget(refresh_btn)
        root.addLayout(header_row)

        # Scroll area for content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setSpacing(12)
        content_layout.setContentsMargins(0, 0, 8, 0)

        # Top row: weather + email + calendar
        top_row = QHBoxLayout()

        # Weather
        weather_box = QGroupBox("Weather")
        wl = QVBoxLayout(weather_box)
        wl.setContentsMargins(12, 14, 12, 12)
        weather_btn = QPushButton("Load Weather")
        weather_btn.clicked.connect(self._load_weather)
        self._weather_label = QTextBrowser()
        self._weather_label.setMaximumHeight(255)
        self._weather_label.setHtml("<p style='color:#94a3b8'>Click to load weather.</p>")
        wl.addWidget(weather_btn)
        wl.addWidget(self._weather_label)
        top_row.addWidget(weather_box)

        # Email
        email_box = QGroupBox("Gmail — Unread")
        el = QVBoxLayout(email_box)
        el.setContentsMargins(12, 14, 12, 12)
        email_btn_row = QHBoxLayout()
        email_auth_btn = QPushButton("Connect")
        email_auth_btn.setFixedWidth(90)
        email_auth_btn.clicked.connect(self._auth_gmail)
        email_btn = QPushButton("Load Emails")
        email_btn.setObjectName("primary")
        email_btn.setFixedWidth(110)
        email_btn.clicked.connect(self._load_emails)
        email_summary_btn = QPushButton("Summarize")
        email_summary_btn.setFixedWidth(100)
        email_summary_btn.clicked.connect(self._summarize_emails)
        email_read_btn = QPushButton("Mark All Read")
        email_read_btn.setFixedWidth(110)
        email_read_btn.clicked.connect(self._mark_all_read)
        email_btn_row.addWidget(email_auth_btn)
        email_btn_row.addWidget(email_btn)
        email_btn_row.addWidget(email_summary_btn)
        email_btn_row.addWidget(email_read_btn)
        email_btn_row.addStretch()
        self._email_browser = QTextBrowser()
        self._email_browser.setMaximumHeight(180)
        self._email_browser.setPlainText("Click to load unread emails.")
        el.addLayout(email_btn_row)
        el.addWidget(self._email_browser)
        top_row.addWidget(email_box)

        # Calendar
        cal_box = QGroupBox("Google Calendar — Today")
        cl = QVBoxLayout(cal_box)
        cl.setContentsMargins(12, 14, 12, 12)
        cal_btn_row = QHBoxLayout()
        cal_auth_btn = QPushButton("Connect")
        cal_auth_btn.setFixedWidth(90)
        cal_auth_btn.clicked.connect(self._auth_calendar)
        cal_btn = QPushButton("Load Events")
        cal_btn.setObjectName("primary")
        cal_btn.setFixedWidth(110)
        cal_btn.clicked.connect(self._load_calendar)
        cal_upcoming_btn = QPushButton("Next 5 Days")
        cal_upcoming_btn.setFixedWidth(110)
        cal_upcoming_btn.clicked.connect(lambda: self._load_calendar(days=5))
        cal_btn_row.addWidget(cal_auth_btn)
        cal_btn_row.addWidget(cal_btn)
        cal_btn_row.addWidget(cal_upcoming_btn)
        cal_btn_row.addStretch()
        self._cal_browser = QTextBrowser()
        self._cal_browser.setMaximumHeight(180)
        self._cal_browser.setPlainText("Click to load today's events.")
        cl.addLayout(cal_btn_row)
        cl.addWidget(self._cal_browser)
        top_row.addWidget(cal_box)

        content_layout.addLayout(top_row)

        # AI Commentary
        ai_box = QGroupBox("AI Personal Briefing")
        ai_layout = QVBoxLayout(ai_box)
        ai_layout.setContentsMargins(12, 14, 12, 12)
        ai_btn_row = QHBoxLayout()
        self._ai_btn = QPushButton("Generate Briefing")
        self._ai_btn.setObjectName("primary")
        self._ai_btn.setFixedWidth(180)
        self._ai_btn.clicked.connect(self._get_commentary)
        ai_btn_row.addWidget(self._ai_btn)
        ai_btn_row.addStretch()
        self._ai_browser = QTextBrowser()
        self._ai_browser.setMinimumHeight(200)
        self._ai_browser.setOpenExternalLinks(True)
        ai_layout.addLayout(ai_btn_row)
        ai_layout.addWidget(self._ai_browser)
        content_layout.addWidget(ai_box)

        content_layout.addStretch()
        scroll.setWidget(content)
        root.addWidget(scroll)

    def _refresh_all(self):
        self._load_weather()
        self._load_emails()
        self._load_calendar()
        self._get_commentary()

    # ── Weather ───────────────────────────────────────────────────────────────
    def _load_weather(self):
        from utils.config import load_config
        city = load_config().get("city", "")
        if not city:
            self._weather_label.setText("Set your city in Settings to see weather.")
            return
        self._weather_label.setText("Loading…")

        from workers.market_worker import WeatherWorker
        self._weather_worker = WeatherWorker(city)
        self._weather_worker.result.connect(lambda w: self._weather_label.setHtml(_weather_html(w)))
        self._weather_worker.error.connect(lambda e: self._weather_label.setPlainText(f"Error: {e}"))
        self._weather_worker.start()

    # ── Email ─────────────────────────────────────────────────────────────────
    def _auth_gmail(self):
        self._email_browser.setPlainText("Opening Gmail OAuth in your browser...")
        from PyQt6.QtCore import QThread, pyqtSignal

        class _GmailAuthWorker(QThread):
            done = pyqtSignal()
            fail = pyqtSignal(str)

            def run(self):
                try:
                    from utils.email import authenticate_gmail
                    authenticate_gmail()
                    self.done.emit()
                except Exception as e:
                    self.fail.emit(str(e))

        self._gmail_auth_worker = _GmailAuthWorker()
        self._gmail_auth_worker.done.connect(
            lambda: self._email_browser.setPlainText("Gmail connected. Click Load Emails.")
        )
        self._gmail_auth_worker.fail.connect(lambda e: self._email_browser.setPlainText(f"Auth error: {e}"))
        self._gmail_auth_worker.start()

    def _load_emails(self):
        self._email_browser.setPlainText("Loading…")
        from PyQt6.QtCore import QThread, pyqtSignal

        class _EmailWorker(QThread):
            done = pyqtSignal(object)
            fail = pyqtSignal(str)

            def run(self):
                try:
                    from utils.email import get_gmail_service, fetch_unread_emails
                    svc = get_gmail_service()
                    if svc is None:
                        self.fail.emit("Not authenticated. Click Connect to complete Gmail OAuth.")
                        return
                    self.done.emit(fetch_unread_emails(svc, limit=10))
                except Exception as e:
                    self.fail.emit(str(e))

        self._email_worker = _EmailWorker()
        self._email_worker.done.connect(self._on_emails)
        self._email_worker.fail.connect(lambda e: self._email_browser.setPlainText(e))
        self._email_worker.start()

    def _on_emails(self, emails):
        self._emails = emails or []
        if not emails:
            self._email_browser.setPlainText("No unread emails.")
            return
        rows = "".join(
            f"<tr><td style='padding:5px 0;border-bottom:1px solid #0f1929'>"
            f"<b style='color:#EEF2FF'>{e.get('subject','(no subject)')}</b><br>"
            f"<span style='color:#475569;font-size:11px'>{e.get('from','')} | {e.get('date','')}</span><br>"
            f"<span style='color:#94a3b8;font-size:12px'>{e.get('snippet','')}</span></td></tr>"
            for e in emails
        )
        self._email_browser.setHtml(
            f"<html><body style='background:#070d1a;color:#EEF2FF;font-family:Segoe UI;padding:8px'>"
            f"<table width='100%'>{rows}</table></body></html>"
        )

    def _summarize_emails(self):
        if not self._emails:
            self._email_browser.setPlainText("Load unread emails before summarizing.")
            return
        from utils.config import load_config

        config = load_config()
        if not config.get("api_key"):
            self._email_browser.setPlainText("No API key configured. Go to Settings.")
            return
        self._email_browser.setPlainText("Summarizing unread emails...")
        from PyQt6.QtCore import QThread, pyqtSignal

        class _EmailSummaryWorker(QThread):
            done = pyqtSignal(str)
            fail = pyqtSignal(str)

            def __init__(self, emails, config):
                super().__init__()
                self.emails = emails
                self.config = config

            def run(self):
                try:
                    from utils.llm import chat_completions_create

                    email_context = "\n".join(
                        f"- From: {e['from']} | Subject: {e['subject']} | {e.get('snippet', '')[:140]}"
                        for e in self.emails[:10]
                    )
                    response = chat_completions_create(
                        messages=[
                            {
                                "role": "system",
                                "content": (
                                    "You are a concise email summarizer. Group by priority, "
                                    "highlight action items, and note anything urgent."
                                ),
                            },
                            {
                                "role": "user",
                                "content": f"Summarize these emails for my morning digest:\n\n{email_context}",
                            },
                        ],
                        temperature=0.5,
                        model=self.config["model"],
                        api_key=self.config.get("api_key") or None,
                        base_url=self.config.get("base_url") or None,
                    )
                    self.done.emit(response["content"])
                except Exception as e:
                    self.fail.emit(str(e))

        self._email_summary_worker = _EmailSummaryWorker(self._emails, config)
        self._email_summary_worker.done.connect(lambda t: self._email_browser.setHtml(_render_md(t)))
        self._email_summary_worker.fail.connect(lambda e: self._email_browser.setPlainText(f"Summary error: {e}"))
        self._email_summary_worker.start()

    def _mark_all_read(self):
        if not self._emails:
            self._email_browser.setPlainText("No loaded unread emails to mark as read.")
            return
        self._email_browser.setPlainText("Marking loaded emails as read...")
        from PyQt6.QtCore import QThread, pyqtSignal

        class _MarkReadWorker(QThread):
            done = pyqtSignal()
            fail = pyqtSignal(str)

            def __init__(self, emails):
                super().__init__()
                self.emails = emails

            def run(self):
                try:
                    from utils.email import get_gmail_service, mark_as_read

                    svc = get_gmail_service()
                    for email in self.emails:
                        mark_as_read(svc, email["id"])
                    self.done.emit()
                except Exception as e:
                    self.fail.emit(str(e))

        self._mark_read_worker = _MarkReadWorker(self._emails)
        self._mark_read_worker.done.connect(self._on_marked_read)
        self._mark_read_worker.fail.connect(lambda e: self._email_browser.setPlainText(f"Mark read error: {e}"))
        self._mark_read_worker.start()

    def _on_marked_read(self):
        self._emails = []
        self._email_browser.setPlainText("Marked loaded emails as read.")

    # ── Calendar ──────────────────────────────────────────────────────────────
    def _auth_calendar(self):
        self._cal_browser.setPlainText("Opening Google Calendar OAuth in your browser...")
        from PyQt6.QtCore import QThread, pyqtSignal

        class _CalendarAuthWorker(QThread):
            done = pyqtSignal()
            fail = pyqtSignal(str)

            def run(self):
                try:
                    from utils.calendar import authenticate_calendar
                    authenticate_calendar()
                    self.done.emit()
                except Exception as e:
                    self.fail.emit(str(e))

        self._calendar_auth_worker = _CalendarAuthWorker()
        self._calendar_auth_worker.done.connect(
            lambda: self._cal_browser.setPlainText("Calendar connected. Click Load Events.")
        )
        self._calendar_auth_worker.fail.connect(lambda e: self._cal_browser.setPlainText(f"Auth error: {e}"))
        self._calendar_auth_worker.start()

    def _load_calendar(self, days=None):
        self._cal_browser.setPlainText("Loading…")
        from PyQt6.QtCore import QThread, pyqtSignal

        class _CalWorker(QThread):
            done = pyqtSignal(object)
            fail = pyqtSignal(str)

            def __init__(self, days=None):
                super().__init__()
                self.days = days

            def run(self):
                try:
                    from utils.calendar import get_calendar_service, fetch_todays_events, fetch_upcoming_events
                    svc = get_calendar_service()
                    if svc is None:
                        self.fail.emit("Not authenticated. Click Connect to complete Calendar OAuth.")
                        return
                    if self.days:
                        self.done.emit(fetch_upcoming_events(svc, days=self.days))
                    else:
                        self.done.emit(fetch_todays_events(svc))
                except Exception as e:
                    self.fail.emit(str(e))

        self._cal_worker = _CalWorker(days=days)
        self._cal_worker.done.connect(self._on_calendar)
        self._cal_worker.fail.connect(lambda e: self._cal_browser.setPlainText(e))
        self._cal_worker.start()

    def _on_calendar(self, events):
        if not events:
            self._cal_browser.setPlainText("No events today.")
            return
        rows = "".join(
            f"<tr><td style='padding:7px 0;border-bottom:1px solid #0f1929'>"
            f"<b style='color:#EEF2FF'>{e.get('title') or e.get('summary') or '(No title)'}</b><br>"
            f"<span style='color:#6366F1;font-size:12px;font-weight:700'>{_calendar_time_label(e)}</span>"
            f"{_calendar_location(e)}"
            f"{_calendar_description(e)}</td></tr>"
            for e in events
        )
        self._cal_browser.setHtml(
            f"<html><body style='background:#070d1a;color:#EEF2FF;font-family:Segoe UI;padding:8px'>"
            f"<table width='100%'>{rows}</table></body></html>"
        )

    # ── AI Commentary ────────────────────────────────────────────────────────
    def _get_commentary(self):
        from utils.config import load_config, load_portfolio
        config = load_config()
        if not config.get("api_key"):
            self._ai_browser.setHtml("<p style='color:#F43F5E;padding:12px'>No API key — go to Settings.</p>")
            return
        portfolio = load_portfolio()
        self._ai_btn.setEnabled(False)
        self._ai_btn.setText("Generating…")
        self._ai_browser.setHtml("<p style='color:#475569;padding:12px'>Generating commentary…</p>")

        from workers.llm_worker import BriefingLLMWorker
        self._llm_worker = BriefingLLMWorker(portfolio, config)
        self._llm_worker.result.connect(lambda t: self._ai_browser.setHtml(_render_md(t)))
        self._llm_worker.error.connect(
            lambda e: self._ai_browser.setHtml(f"<p style='color:#F43F5E;padding:12px'>Error: {e}</p>")
        )
        self._llm_worker.finished.connect(lambda: (
            self._ai_btn.setEnabled(True),
            self._ai_btn.setText("Generate Briefing"),
        ))
        self._llm_worker.start()
