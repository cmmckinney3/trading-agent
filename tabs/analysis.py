from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTextBrowser, QGridLayout, QGroupBox,
    QComboBox, QSplitter, QFrame,
)
from PyQt6.QtCore import Qt
from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.patches import Rectangle
import markdown as md_lib


def _render_md(text):
    body = md_lib.markdown(text or "", extensions=["tables", "fenced_code"])
    return f"""<html><head><style>
    body{{font-family:'Segoe UI',sans-serif;color:#EEF2FF;background:#070d1a;padding:14px;line-height:1.7;}}
    h1,h2,h3{{color:#c7d2fe;margin-top:12px;}}
    strong{{color:#a5b4fc;}}
    code{{background:#1e293b;padding:2px 6px;border-radius:3px;color:#22D3EE;font-family:monospace;}}
    pre{{background:#0f1929;padding:12px;border-radius:6px;overflow-x:auto;}}
    table{{border-collapse:collapse;width:100%;margin:8px 0;}}
    th{{background:#0a1020;color:#94a3b8;padding:8px 12px;text-align:left;border-bottom:1px solid #1e293b;}}
    td{{padding:8px 12px;border-bottom:1px solid #0f1929;}}
    p{{margin:6px 0;}}
    </style></head><body>{body}</body></html>"""


class CandlestickCanvas(FigureCanvasQTAgg):
    def __init__(self):
        self.fig = Figure(figsize=(10, 3.2), facecolor="#070d1a", tight_layout=True)
        super().__init__(self.fig)
        self.ax = self.fig.add_subplot(111)
        self._style_ax()

    def _style_ax(self):
        self.ax.set_facecolor("#070d1a")
        self.ax.tick_params(colors="#475569", labelsize=9)
        for spine in self.ax.spines.values():
            spine.set_color("#1e293b")
        self.fig.patch.set_facecolor("#070d1a")

    def plot(self, df, tech=None):
        self.ax.clear()
        self._style_ax()

        if df is None or df.empty:
            self.ax.text(0.5, 0.5, "No chart data", transform=self.ax.transAxes,
                         ha="center", va="center", color="#475569", fontsize=12)
            self.draw()
            return

        data = df.tail(90).reset_index(drop=True)
        n = len(data)

        for i, row in data.iterrows():
            is_bull = row["Close"] >= row["Open"]
            color = "#10B981" if is_bull else "#F43F5E"
            lo = min(row["Open"], row["Close"])
            body_h = max(abs(row["Close"] - row["Open"]), row["Close"] * 0.001)
            self.ax.add_patch(Rectangle((i - 0.38, lo), 0.76, body_h, color=color, zorder=2))
            self.ax.plot([i, i], [row["Low"], row["High"]], color=color, lw=0.7, zorder=1)

        closes = data["Close"].values
        if tech and n >= 20:
            sma20 = [closes[max(0, j - 19):j + 1].mean() for j in range(n)]
            self.ax.plot(range(n), sma20, color="#6366F1", lw=1.3, label="SMA20", zorder=3)

        if tech and n >= 50:
            sma50 = [closes[max(0, j - 49):j + 1].mean() for j in range(n)]
            self.ax.plot(range(n), sma50, color="#F59E0B", lw=1.3, label="SMA50", zorder=3)

        self.ax.set_xlim(-0.5, n - 0.5)
        self.ax.autoscale_view(scalex=False)
        self.ax.yaxis.set_major_formatter(lambda x, _: f"${x:.2f}")
        self.ax.tick_params(axis="x", bottom=False, labelbottom=False)

        if tech:
            legend = self.ax.legend(
                facecolor="#0a1020", edgecolor="#1e293b",
                labelcolor="#94a3b8", fontsize=8, loc="upper left",
            )

        self.fig.tight_layout(pad=0.8)
        self.draw()


class MetricCard(QFrame):
    def __init__(self, title):
        super().__init__()
        self.setStyleSheet(
            "QFrame{background:#0a1020;border:1px solid #1e293b;border-radius:8px;}"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(3)

        lbl = QLabel(title.upper())
        lbl.setStyleSheet("font-size:10px;color:#475569;font-weight:700;letter-spacing:1px;background:transparent;border:none;")
        self._val = QLabel("—")
        self._val.setStyleSheet("font-size:20px;font-weight:700;color:#EEF2FF;background:transparent;border:none;")
        self._sub = QLabel("")
        self._sub.setStyleSheet("font-size:11px;color:#64748b;background:transparent;border:none;")

        layout.addWidget(lbl)
        layout.addWidget(self._val)
        layout.addWidget(self._sub)

    def set(self, value, subtitle="", color=None):
        self._val.setText(str(value))
        self._sub.setText(str(subtitle))
        c = color or "#EEF2FF"
        self._val.setStyleSheet(f"font-size:20px;font-weight:700;color:{c};background:transparent;border:none;")


class AnalysisTab(QWidget):
    def __init__(self):
        super().__init__()
        self._worker = None
        self._rec_worker = None
        self._current_ticker = ""
        self._setup_ui()

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(10)

        title = QLabel("Ticker Analysis")
        title.setStyleSheet("font-size:18px;font-weight:700;color:#EEF2FF;")
        root.addWidget(title)

        # Input row
        row = QHBoxLayout()
        self._ticker_input = QLineEdit()
        self._ticker_input.setPlaceholderText("Symbol (e.g. NVDA)")
        self._ticker_input.setMaximumWidth(200)
        self._ticker_input.returnPressed.connect(self._run_analysis)

        self._period_combo = QComboBox()
        for t in ["1 Month", "3 Months", "6 Months", "1 Year"]:
            self._period_combo.addItem(t)
        self._period_combo.setCurrentIndex(1)
        self._period_combo.setMaximumWidth(120)

        self._analyze_btn = QPushButton("Analyze")
        self._analyze_btn.setObjectName("primary")
        self._analyze_btn.setFixedWidth(100)
        self._analyze_btn.clicked.connect(self._run_analysis)

        row.addWidget(self._ticker_input)
        row.addWidget(self._period_combo)
        row.addWidget(self._analyze_btn)
        row.addStretch()
        root.addLayout(row)

        # Metrics
        metrics_row = QHBoxLayout()
        self._m_price = MetricCard("Price")
        self._m_change = MetricCard("Change")
        self._m_volume = MetricCard("Volume")
        self._m_rsi = MetricCard("RSI (14)")
        self._m_earnings = MetricCard("Next Earnings")
        for m in [self._m_price, self._m_change, self._m_volume, self._m_rsi, self._m_earnings]:
            metrics_row.addWidget(m)
        root.addLayout(metrics_row)

        # Chart
        self._chart = CandlestickCanvas()
        self._chart.setMinimumHeight(240)
        self._chart.setMaximumHeight(300)
        root.addWidget(self._chart)

        # Bottom: technicals | news + recommendation
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Technicals
        tech_box = QGroupBox("Technicals")
        tech_grid = QGridLayout(tech_box)
        tech_grid.setSpacing(10)
        tech_grid.setContentsMargins(12, 16, 12, 12)
        self._tech = {}
        fields = [
            ("SMA 20", "sma20"), ("SMA 50", "sma50"), ("EMA 9", "ema9"),
            ("MACD", "macd"), ("Signal", "macd_signal"), ("BB Upper", "bb_upper"),
            ("BB Lower", "bb_lower"), ("ATR", "atr"), ("Vol Ratio", "vol_ratio"),
        ]
        for i, (label, key) in enumerate(fields):
            r, c = divmod(i, 3)
            cell = QWidget()
            cell.setStyleSheet("background:transparent;")
            cl = QVBoxLayout(cell)
            cl.setContentsMargins(0, 0, 0, 0)
            cl.setSpacing(2)
            lbl = QLabel(label)
            lbl.setStyleSheet("font-size:10px;color:#475569;font-weight:600;text-transform:uppercase;")
            val = QLabel("—")
            val.setStyleSheet("font-size:13px;font-weight:600;color:#EEF2FF;")
            self._tech[key] = val
            cl.addWidget(lbl)
            cl.addWidget(val)
            tech_grid.addWidget(cell, r, c)
        splitter.addWidget(tech_box)

        # Right: news + rec
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(8)

        news_box = QGroupBox("Recent News")
        news_layout = QVBoxLayout(news_box)
        news_layout.setContentsMargins(8, 12, 8, 8)
        self._news = QTextBrowser()
        self._news.setMaximumHeight(130)
        self._news.setOpenExternalLinks(True)
        news_layout.addWidget(self._news)
        rl.addWidget(news_box)

        rec_box = QGroupBox("AI Recommendation")
        rec_layout = QVBoxLayout(rec_box)
        rec_layout.setContentsMargins(8, 12, 8, 8)
        self._rec_btn = QPushButton("Get AI Recommendation")
        self._rec_btn.setObjectName("primary")
        self._rec_browser = QTextBrowser()
        self._rec_browser.setOpenExternalLinks(True)
        rec_layout.addWidget(self._rec_btn)
        rec_layout.addWidget(self._rec_browser)
        rl.addWidget(rec_box)
        splitter.addWidget(right)
        splitter.setSizes([380, 580])
        root.addWidget(splitter)

        self._rec_btn.clicked.connect(self._get_recommendation)

    # ── period helper ──────────────────────────────────────────────────────────
    def _period_code(self):
        return {"1 Month": "1mo", "3 Months": "3mo", "6 Months": "6mo", "1 Year": "1y"}.get(
            self._period_combo.currentText(), "3mo"
        )

    # ── Analysis ──────────────────────────────────────────────────────────────
    def _run_analysis(self):
        ticker = self._ticker_input.text().strip().upper()
        if not ticker:
            return
        self._current_ticker = ticker
        self._analyze_btn.setEnabled(False)
        self._analyze_btn.setText("Loading…")
        self._rec_browser.clear()

        from workers.market_worker import AnalysisWorker
        self._worker = AnalysisWorker(ticker, self._period_code())
        self._worker.result.connect(self._on_result)
        self._worker.error.connect(self._on_error)
        self._worker.finished.connect(lambda: (
            self._analyze_btn.setEnabled(True),
            self._analyze_btn.setText("Analyze"),
        ))
        self._worker.start()

    def _on_result(self, data):
        quote = data.get("quote") or {}
        tech = data.get("technicals") or {}
        history = data.get("history")
        news = data.get("news") or []
        earnings = data.get("earnings")

        if quote:
            self._m_price.set(f"${quote['price']:.2f}")
            chg, pct = quote["change"], quote["change_pct"]
            sign = "+" if chg >= 0 else ""
            col = "#10B981" if chg >= 0 else "#F43F5E"
            self._m_change.set(f"{sign}{chg:.2f}", f"{sign}{pct:.2f}%", color=col)
            vol = quote.get("volume", 0)
            self._m_volume.set(f"{vol:,}" if vol else "—")

        if tech:
            rsi = tech.get("rsi")
            if rsi:
                rsi_col = "#F59E0B" if rsi > 70 or rsi < 30 else "#10B981"
                self._m_rsi.set(f"{rsi:.1f}", "overbought" if rsi > 70 else ("oversold" if rsi < 30 else "neutral"), color=rsi_col)
            for key, widget in self._tech.items():
                val = tech.get(key)
                if val is not None:
                    widget.setText(f"{val:.4f}" if abs(float(val)) < 0.1 else f"{val:.2f}")
                else:
                    widget.setText("—")

        self._m_earnings.set(earnings or "—")
        self._chart.plot(history, tech)

        if news:
            rows = "".join(
                f"<tr><td style='padding:5px 0;border-bottom:1px solid #0f1929'>"
                f"<span style='color:#475569;font-size:11px'>{n['date']}</span>&nbsp;&nbsp;"
                f"<span style='color:#EEF2FF'>{n['title']}</span>"
                f"<span style='color:#475569'> — {n['publisher']}</span></td></tr>"
                for n in news
            )
            self._news.setHtml(
                f"<html><body style='background:#070d1a;color:#EEF2FF;font-family:Segoe UI;padding:8px'>"
                f"<table width='100%'>{rows}</table></body></html>"
            )
        else:
            self._news.setPlainText("No recent news.")

    def _on_error(self, msg):
        self._m_price.set("Error", color="#F43F5E")
        self._m_change.set(msg[:50])

    # ── Recommendation ────────────────────────────────────────────────────────
    def _get_recommendation(self):
        if not self._current_ticker:
            return
        from utils.config import load_config, load_portfolio
        config = load_config()
        if not config.get("api_key"):
            self._rec_browser.setHtml(
                "<p style='color:#F43F5E;padding:12px'>No API key configured — go to Settings.</p>"
            )
            return
        portfolio = load_portfolio()
        self._rec_btn.setEnabled(False)
        self._rec_btn.setText("Thinking…")
        self._rec_browser.setHtml("<p style='color:#475569;padding:12px'>Fetching recommendation…</p>")

        from workers.llm_worker import RecommendationWorker
        self._rec_worker = RecommendationWorker(self._current_ticker, portfolio, config)
        self._rec_worker.result.connect(lambda t: self._rec_browser.setHtml(_render_md(t)))
        self._rec_worker.error.connect(
            lambda e: self._rec_browser.setHtml(f"<p style='color:#F43F5E;padding:12px'>Error: {e}</p>")
        )
        self._rec_worker.finished.connect(lambda: (
            self._rec_btn.setEnabled(True),
            self._rec_btn.setText("Get AI Recommendation"),
        ))
        self._rec_worker.start()
