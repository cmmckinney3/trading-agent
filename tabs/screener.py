from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QTextBrowser, QHeaderView,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
import markdown as md_lib


def _render_md(text):
    body = md_lib.markdown(text or "", extensions=["tables", "fenced_code"])
    return f"""<html><head><style>
    body{{font-family:'Segoe UI',sans-serif;color:#EEF2FF;background:#070d1a;padding:14px;line-height:1.7;}}
    h1,h2,h3{{color:#c7d2fe;}}strong{{color:#a5b4fc;}}
    code{{background:#1e293b;padding:2px 6px;border-radius:3px;color:#22D3EE;font-size:12px;}}
    pre{{background:#0f1929;padding:10px;border-radius:6px;}}
    table{{border-collapse:collapse;width:100%;}}
    th{{background:#0a1020;color:#94a3b8;padding:8px 12px;text-align:left;border-bottom:1px solid #1e293b;}}
    td{{padding:8px 12px;border-bottom:1px solid #0f1929;}}
    p{{margin:4px 0;}}
    </style></head><body>{body}</body></html>"""


class ScreenerTab(QWidget):
    def __init__(self):
        super().__init__()
        self._screener_worker = None
        self._llm_worker = None
        self._results = []
        self._setup_ui()

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(10)

        # Header
        header_row = QHBoxLayout()
        title = QLabel("Momentum Screener")
        title.setStyleSheet("font-size:18px;font-weight:700;color:#EEF2FF;")
        caption = QLabel("Screens your watchlist for high-momentum swing trade setups.")
        caption.setStyleSheet("font-size:12px;color:#475569;")
        self._run_btn = QPushButton("Run Screener")
        self._run_btn.setObjectName("primary")
        self._run_btn.setFixedWidth(130)
        self._run_btn.clicked.connect(self._run_screener)
        header_row.addWidget(title)
        header_row.addSpacing(10)
        header_row.addWidget(caption)
        header_row.addStretch()
        header_row.addWidget(self._run_btn)
        root.addLayout(header_row)

        self._status = QLabel("")
        self._status.setStyleSheet("color:#475569;font-size:12px;")
        root.addWidget(self._status)

        # Results table
        self._table = QTableWidget()
        cols = ["Ticker", "Price", "RSI", "Vol Ratio", "SMA20", "SMA50", "MACD Bullish", "Score"]
        self._table.setColumnCount(len(cols))
        self._table.setHorizontalHeaderLabels(cols)
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._table.setAlternatingRowColors(True)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setMaximumHeight(280)
        root.addWidget(self._table)

        # AI picks
        ai_row = QHBoxLayout()
        self._ai_btn = QPushButton("Get AI Top Picks")
        self._ai_btn.setObjectName("primary")
        self._ai_btn.setFixedWidth(150)
        self._ai_btn.setEnabled(False)
        self._ai_btn.clicked.connect(self._get_ai_picks)
        ai_row.addWidget(self._ai_btn)
        ai_row.addStretch()
        root.addLayout(ai_row)

        self._ai_browser = QTextBrowser()
        self._ai_browser.setOpenExternalLinks(True)
        root.addWidget(self._ai_browser, stretch=1)

    def _run_screener(self):
        from utils.config import load_config
        config = load_config()
        watchlist = config.get("watchlist")

        self._run_btn.setEnabled(False)
        self._run_btn.setText("Scanning…")
        self._status.setText(f"Screening {len(watchlist)} tickers…")
        self._table.setRowCount(0)
        self._ai_browser.clear()
        self._ai_btn.setEnabled(False)

        from workers.market_worker import ScreenerWorker
        self._screener_worker = ScreenerWorker(watchlist)
        self._screener_worker.result.connect(self._on_screener_result)
        self._screener_worker.error.connect(lambda e: self._status.setText(f"Error: {e}"))
        self._screener_worker.finished.connect(lambda: (
            self._run_btn.setEnabled(True),
            self._run_btn.setText("Run Screener"),
        ))
        self._screener_worker.start()

    def _on_screener_result(self, results):
        self._results = results
        count = len(results)
        self._status.setText(f"Found {count} qualifying ticker{'s' if count != 1 else ''}.")
        self._table.setRowCount(count)

        for i, r in enumerate(results):
            def _cell(text, color=None):
                item = QTableWidgetItem(str(text))
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if color:
                    item.setForeground(QColor(color))
                return item

            above20 = r.get("above_sma20")
            above50 = r.get("above_sma50")
            macd_bull = r.get("macd_bullish")
            rsi = r.get("rsi", 0) or 0
            rsi_col = "#F59E0B" if rsi > 70 else ("#10B981" if 45 < rsi < 70 else "#F43F5E")

            self._table.setItem(i, 0, _cell(r.get("ticker", ""), "#EEF2FF"))
            self._table.setItem(i, 1, _cell(f"${r.get('price', 0):.2f}"))
            self._table.setItem(i, 2, _cell(f"{rsi:.1f}", rsi_col))
            self._table.setItem(i, 3, _cell(f"{r.get('vol_ratio', 0):.2f}"))
            self._table.setItem(i, 4, _cell("Yes" if above20 else "No", "#10B981" if above20 else "#F43F5E"))
            self._table.setItem(i, 5, _cell("Yes" if above50 else "No", "#10B981" if above50 else "#F43F5E"))
            self._table.setItem(i, 6, _cell("Yes" if macd_bull else "No", "#10B981" if macd_bull else "#64748b"))
            self._table.setItem(i, 7, _cell(str(r.get("score", 0)), "#F59E0B"))

        if results:
            self._ai_btn.setEnabled(True)

    def _get_ai_picks(self):
        from utils.config import load_config, load_portfolio
        config = load_config()
        if not config.get("api_key"):
            self._ai_browser.setHtml("<p style='color:#F43F5E;padding:12px'>No API key — go to Settings.</p>")
            return
        portfolio = load_portfolio()

        self._ai_btn.setEnabled(False)
        self._ai_btn.setText("Thinking…")
        self._ai_browser.setHtml("<p style='color:#475569;padding:12px'>Analyzing screener results…</p>")

        from workers.llm_worker import ScreenerLLMWorker
        watchlist = config.get("watchlist")
        self._llm_worker = ScreenerLLMWorker(portfolio, config, watchlist)
        self._llm_worker.result.connect(lambda t: self._ai_browser.setHtml(_render_md(t)))
        self._llm_worker.error.connect(
            lambda e: self._ai_browser.setHtml(f"<p style='color:#F43F5E;padding:12px'>Error: {e}</p>")
        )
        self._llm_worker.finished.connect(lambda: (
            self._ai_btn.setEnabled(True),
            self._ai_btn.setText("Get AI Top Picks"),
        ))
        self._llm_worker.start()
