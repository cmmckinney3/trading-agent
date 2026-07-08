from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QMainWindow, QPushButton, QScrollArea, QStatusBar,
    QTabWidget, QVBoxLayout, QWidget, QLabel,
)
from PyQt6.QtCore import Qt

from tabs.briefing import BriefingTab
from tabs.chat import ChatTab
from tabs.screener import ScreenerTab
from tabs.analysis import AnalysisTab
from tabs.positions import PositionsTab
from tabs.settings import SettingsTab
from tabs.journal import JournalTab
from tabs.sysadmin import SysadminTab
from tabs.developer import DeveloperTab
from tabs.weather_golf import WeatherGolfTab
from tabs.code_agent import CodeAgentTab


class PortfolioSidebar(QFrame):
    def __init__(self):
        super().__init__()
        self._worker = None
        self.setObjectName("portfolioSidebar")
        self.setFixedWidth(260)
        self._setup_ui()
        self.refresh(use_prices=False)

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(12)

        brand = QLabel("LocalOps AI")
        brand.setStyleSheet("font-size:18px;font-weight:800;color:#EEF2FF;")
        sub = QLabel("Personal operations terminal")
        sub.setStyleSheet("font-size:10px;color:#64748b;text-transform:uppercase;letter-spacing:1px;")
        root.addWidget(brand)
        root.addWidget(sub)

        self._refresh_btn = QPushButton("Refresh Prices")
        self._refresh_btn.setObjectName("primary")
        self._refresh_btn.clicked.connect(lambda: self.refresh(use_prices=True))
        root.addWidget(self._refresh_btn)

        self._total = self._metric("Total Account", "$0.00")
        self._cash = self._metric("Cash", "$0.00")
        root.addWidget(self._total)
        root.addWidget(self._cash)

        holdings_label = QLabel("POSITIONS")
        holdings_label.setStyleSheet("font-size:10px;color:#64748b;font-weight:700;letter-spacing:1px;")
        root.addWidget(holdings_label)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._positions_widget = QWidget()
        self._positions_layout = QVBoxLayout(self._positions_widget)
        self._positions_layout.setContentsMargins(0, 0, 0, 0)
        self._positions_layout.setSpacing(8)
        self._positions_layout.addStretch()
        scroll.setWidget(self._positions_widget)
        root.addWidget(scroll, stretch=1)

    def _metric(self, title, value):
        card = QFrame()
        card.setStyleSheet("QFrame{background:#0a1020;border:1px solid #1e293b;border-radius:8px;}")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 9, 12, 9)
        label = QLabel(title.upper())
        label.setStyleSheet("font-size:10px;color:#64748b;font-weight:700;background:transparent;")
        val = QLabel(value)
        val.setStyleSheet("font-size:20px;font-weight:800;color:#EEF2FF;background:transparent;")
        layout.addWidget(label)
        layout.addWidget(val)
        card._value = val
        return card

    def refresh(self, use_prices=True):
        from utils.config import load_portfolio

        portfolio = load_portfolio()
        positions = portfolio.get("positions", [])
        if not use_prices:
            self._populate(positions, portfolio.get("cash", 0.0))
            return
        if self._worker is not None:
            return
        if not positions:
            self._populate([], portfolio.get("cash", 0.0))
            return

        self._refresh_btn.setEnabled(False)
        self._refresh_btn.setText("Refreshing...")
        from workers.market_worker import PortfolioWorker

        self._worker = PortfolioWorker(positions)
        self._worker.result.connect(
            lambda data: self._populate(data.get("positions", []), portfolio.get("cash", 0.0))
        )
        self._worker.error.connect(lambda _: self._populate(positions, portfolio.get("cash", 0.0)))
        self._worker.finished.connect(self._refresh_done)
        self._worker.start()

    def _refresh_done(self):
        self._worker = None
        self._refresh_btn.setEnabled(True)
        self._refresh_btn.setText("Refresh Prices")

    def _populate(self, positions, cash):
        while self._positions_layout.count() > 1:
            item = self._positions_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        total = 0.0
        for pos in positions:
            value = pos.get("value")
            if value is None:
                value = float(pos.get("shares", 0) or 0) * float(pos.get("cost_basis", 0) or 0)
            total += value or 0.0
            self._positions_layout.insertWidget(0, self._position_row(pos, value))

        self._total._value.setText(f"${total + cash:,.2f}")
        self._cash._value.setText(f"${cash:,.2f}")

        if not positions:
            empty = QLabel("No positions yet.")
            empty.setStyleSheet("color:#64748b;font-size:12px;")
            self._positions_layout.insertWidget(0, empty)

    def _position_row(self, pos, value):
        row = QFrame()
        row.setStyleSheet("QFrame{background:#070d1a;border:1px solid #1e293b;border-radius:8px;}")
        layout = QHBoxLayout(row)
        layout.setContentsMargins(10, 8, 10, 8)
        left = QLabel(f"{pos.get('ticker', '')}\n{pos.get('shares', 0)} shares")
        left.setStyleSheet("font-size:12px;color:#EEF2FF;background:transparent;")
        right = QLabel(f"${value:,.2f}")
        change = pos.get("change_pct")
        color = "#10B981" if change is None or change >= 0 else "#F43F5E"
        if change is not None:
            right.setText(f"${value:,.2f}\n{change:+.2f}%")
        right.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        right.setStyleSheet(f"font-size:12px;font-weight:700;color:{color};background:transparent;")
        layout.addWidget(left)
        layout.addStretch()
        layout.addWidget(right)
        return row


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("LocalOps AI")
        self.resize(1400, 860)
        self.setMinimumSize(900, 600)

        self._tabs = QTabWidget()
        self._tabs.setDocumentMode(True)
        self._tabs.setTabPosition(QTabWidget.TabPosition.North)
        self._sidebar = PortfolioSidebar()

        self._briefing = BriefingTab()
        self._chat = ChatTab()
        self._screener = ScreenerTab()
        self._analysis = AnalysisTab()
        self._positions = PositionsTab()
        self._journal = JournalTab()
        self._sysadmin = SysadminTab()
        self._developer = DeveloperTab()
        self._weather_golf = WeatherGolfTab()
        self._code_agent = CodeAgentTab()
        self._settings = SettingsTab()

        tab_defs = [
            ("Morning Briefing", self._briefing),
            ("Chat", self._chat),
            ("Sysadmin", self._sysadmin),
            ("Developer", self._developer),
            ("Weather & Golf", self._weather_golf),
            ("Screener", self._screener),
            ("Ticker Analysis", self._analysis),
            ("Positions", self._positions),
            ("Journal", self._journal),
            ("Code Agent", self._code_agent),
            ("Settings", self._settings),
        ]

        for name, widget in tab_defs:
            self._tabs.addTab(widget, name)

        self._positions.portfolio_changed.connect(lambda: self._sidebar.refresh(use_prices=False))

        shell = QWidget()
        shell_layout = QHBoxLayout(shell)
        shell_layout.setContentsMargins(0, 0, 0, 0)
        shell_layout.setSpacing(0)
        shell_layout.addWidget(self._sidebar)
        shell_layout.addWidget(self._tabs, stretch=1)
        self.setCentralWidget(shell)

        # Status bar
        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)
        self._status_bar.showMessage("TradeDesk AI  —  ready")

        # Refresh positions on tab switch
        self._tabs.currentChanged.connect(self._on_tab_change)

    def _on_tab_change(self, index):
        # Reload journal & positions when switching to those tabs
        if self._tabs.widget(index) is self._positions:
            self._positions._load_portfolio()
            self._sidebar.refresh(use_prices=False)
        elif self._tabs.widget(index) is self._journal:
            self._journal._load()
        elif self._tabs.widget(index) is self._settings:
            self._settings._load()
