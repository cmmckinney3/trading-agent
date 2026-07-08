from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)


class _GolfWeatherWorker(QThread):
    done = pyqtSignal(object)
    fail = pyqtSignal(str)

    def __init__(self, city):
        super().__init__()
        self.city = city

    def run(self):
        try:
            from utils.personal_ops import get_golf_weather
            self.done.emit(get_golf_weather(self.city))
        except Exception as exc:
            self.fail.emit(str(exc))


def _rating_color(score):
    if score >= 82:
        return "#10B981"
    if score >= 65:
        return "#22D3EE"
    if score >= 45:
        return "#F59E0B"
    return "#F43F5E"


def _metric(label, value, accent="#EEF2FF"):
    return f"""
    <td style='padding:12px;border:1px solid #1e293b;border-radius:8px;background:#0a1020'>
      <div style='font-size:10px;color:#64748b;font-weight:800;letter-spacing:1px'>{label}</div>
      <div style='font-size:18px;color:{accent};font-weight:900;margin-top:4px'>{value}</div>
    </td>
    """


def _forecast_html(weather):
    cards = []
    for day in (weather.get("forecast") or [])[:3]:
        hours = day.get("hourly") or [{}]
        midday = hours[4] if len(hours) > 4 else hours[0]
        desc = midday.get("weatherDesc", [{}])[0].get("value", "")
        chance_rain = midday.get("chanceofrain", "?")
        cards.append(
            "<td style='padding:12px;border:1px solid #1e293b;border-radius:8px;background:#070d1a'>"
            f"<div style='font-size:11px;color:#64748b;font-weight:800'>{day.get('date', '')}</div>"
            f"<div style='font-size:20px;color:#EEF2FF;font-weight:900;margin-top:4px'>{day.get('maxtempF', '?')} / {day.get('mintempF', '?')} F</div>"
            f"<div style='font-size:12px;color:#94a3b8;margin-top:3px'>{desc}</div>"
            f"<div style='font-size:12px;color:#22D3EE;margin-top:6px'>Rain chance {chance_rain}%</div>"
            "</td>"
        )
    if not cards:
        return ""
    return (
        "<div style='font-size:10px;color:#64748b;font-weight:900;letter-spacing:1px;margin:16px 0 6px'>COURSE WINDOW</div>"
        "<table cellspacing='8' cellpadding='0' style='width:100%;margin-left:-8px'><tr>"
        + "".join(cards)
        + "</tr></table>"
    )


def _golf_html(data):
    if data.get("error"):
        return f"<p style='color:#F43F5E'>{data['error']}</p>"
    weather = data.get("weather", {})
    score = data.get("score", 0)
    color = _rating_color(score)
    notes = "".join(
        f"<li style='margin:5px 0;color:#CBD5E1'>{note}</li>"
        for note in data.get("notes", [])
    )
    desc = weather.get("description") or "Current conditions"
    forecast = _forecast_html(weather)

    return f"""
    <html><body style='background:#070d1a;color:#EEF2FF;font-family:Segoe UI;padding:14px;line-height:1.5'>
      <div style='display:flex;justify-content:space-between;align-items:flex-start;gap:18px'>
        <div>
          <div style='font-size:11px;color:#64748b;font-weight:900;letter-spacing:1px'>PLAYABILITY</div>
          <div style='font-size:36px;color:{color};font-weight:950;line-height:1;margin-top:5px'>{data.get('rating')}</div>
          <div style='font-size:14px;color:#94a3b8;margin-top:8px'>{data.get('city')} - {desc}</div>
        </div>
        <div style='width:150px;background:#0a1020;border:1px solid #1e293b;border-radius:10px;padding:14px;text-align:center'>
          <div style='font-size:44px;color:{color};font-weight:950;line-height:1'>{score}</div>
          <div style='font-size:11px;color:#64748b;font-weight:800;margin-top:4px'>OUT OF 100</div>
        </div>
      </div>

      <table cellspacing='8' cellpadding='0' style='width:100%;margin:18px 0 0 -8px'>
        <tr>
          {_metric('TEMP', f"{weather.get('temp_f', '?')} F", '#EEF2FF')}
          {_metric('FEELS LIKE', f"{weather.get('feels_like_f', '?')} F", '#c7d2fe')}
          {_metric('WIND', f"{weather.get('wind_mph', '?')} mph {weather.get('wind_dir', '')}", '#22D3EE')}
        </tr>
        <tr>
          {_metric('HUMIDITY', f"{weather.get('humidity', '?')}%", '#EEF2FF')}
          {_metric('VISIBILITY', f"{weather.get('visibility_mi', '?')} mi", '#EEF2FF')}
          {_metric('UV INDEX', weather.get('uv_index', '?'), '#F59E0B')}
        </tr>
      </table>

      <div style='display:flex;gap:14px;margin-top:14px'>
        <div style='flex:1;background:#0a1020;border:1px solid #1e293b;border-radius:8px;padding:12px'>
          <div style='font-size:10px;color:#64748b;font-weight:900;letter-spacing:1px'>ROUND NOTES</div>
          <ul style='margin:8px 0 0 18px;padding:0'>{notes}</ul>
        </div>
      </div>
      {forecast}
    </body></html>
    """


class WeatherGolfTab(QWidget):
    def __init__(self):
        super().__init__()
        self._worker = None
        self._setup_ui()
        self._load_default_city()

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(12)

        header = QHBoxLayout()
        title = QLabel("Weather & Golf")
        title.setStyleSheet("font-size:18px;font-weight:700;color:#EEF2FF;")
        header.addWidget(title)
        header.addStretch()
        root.addLayout(header)

        city_box = QGroupBox("Conditions")
        city_layout = QVBoxLayout(city_box)
        city_layout.setContentsMargins(12, 14, 12, 12)
        row = QHBoxLayout()
        self._city = QLineEdit()
        self._city.setPlaceholderText("City or course location")
        self._check_btn = QPushButton("Check")
        self._check_btn.setObjectName("primary")
        self._check_btn.setFixedWidth(90)
        self._check_btn.clicked.connect(self._check)
        row.addWidget(self._city)
        row.addWidget(self._check_btn)
        city_layout.addLayout(row)
        root.addWidget(city_box)

        score_box = QGroupBox("Golf Playability")
        score_layout = QVBoxLayout(score_box)
        score_layout.setContentsMargins(12, 14, 12, 12)
        self._score = QLabel("Enter a city or use the city from Settings, then check the round conditions.")
        self._score.setWordWrap(True)
        self._score.setStyleSheet("font-size:15px;font-weight:700;color:#EEF2FF;line-height:1.6;")
        self._score_bar = QProgressBar()
        self._score_bar.setRange(0, 100)
        self._score_bar.setValue(0)
        self._score_bar.setTextVisible(False)
        self._score_bar.setFixedHeight(8)
        score_layout.addWidget(self._score)
        score_layout.addWidget(self._score_bar)
        root.addWidget(score_box)

        detail_box = QGroupBox("Round Conditions")
        detail_layout = QVBoxLayout(detail_box)
        detail_layout.setContentsMargins(12, 14, 12, 12)
        self._details = QTextBrowser()
        self._details.setOpenExternalLinks(False)
        self._details.setHtml("<p style='color:#64748b'>No weather loaded.</p>")
        detail_layout.addWidget(self._details)
        root.addWidget(detail_box, stretch=1)

    def _load_default_city(self):
        try:
            from utils.config import load_config
            self._city.setText(load_config().get("city", ""))
        except Exception:
            pass

    def _check(self):
        city = self._city.text().strip()
        if not city or self._worker is not None:
            return
        self._check_btn.setEnabled(False)
        self._check_btn.setText("Checking...")
        self._score.setText("Loading weather and calculating playability...")
        self._score_bar.setValue(0)
        self._details.setHtml("<p style='color:#64748b'>Fetching course conditions...</p>")
        self._worker = _GolfWeatherWorker(city)
        self._worker.done.connect(self._on_done)
        self._worker.fail.connect(self._on_fail)
        self._worker.finished.connect(self._on_finished)
        self._worker.start()

    def _on_done(self, data):
        if data.get("error"):
            self._score.setText(data["error"])
            self._score_bar.setValue(0)
            return
        score = data.get("score", 0)
        color = _rating_color(score)
        self._score.setText(
            f"{data.get('rating')} ({data.get('score')}/100) for {data.get('city')}"
        )
        self._score.setStyleSheet(f"font-size:15px;font-weight:800;color:{color};line-height:1.6;")
        self._score_bar.setValue(score)
        self._score_bar.setStyleSheet(
            f"QProgressBar{{background:#1e293b;border:none;border-radius:4px;}}"
            f"QProgressBar::chunk{{background:{color};border-radius:4px;}}"
        )
        self._details.setHtml(_golf_html(data))

    def _on_fail(self, message):
        self._score.setText(f"Error: {message}")
        self._score_bar.setValue(0)

    def _on_finished(self):
        self._worker = None
        self._check_btn.setEnabled(True)
        self._check_btn.setText("Check")
