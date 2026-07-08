from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTableWidget, QTableWidgetItem, QGroupBox,
    QDoubleSpinBox, QHeaderView, QMessageBox,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor


class PositionsTab(QWidget):
    portfolio_changed = pyqtSignal()

    def __init__(self):
        super().__init__()
        self._worker = None
        self._setup_ui()

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(10)

        # Header
        header_row = QHBoxLayout()
        title = QLabel("Portfolio")
        title.setStyleSheet("font-size:18px;font-weight:700;color:#EEF2FF;")
        self._refresh_btn = QPushButton("Refresh Prices")
        self._refresh_btn.setObjectName("primary")
        self._refresh_btn.clicked.connect(self._refresh)
        header_row.addWidget(title)
        header_row.addStretch()
        header_row.addWidget(self._refresh_btn)
        root.addLayout(header_row)

        # Summary cards
        cards_row = QHBoxLayout()
        self._total_label = self._make_card("Portfolio Value", "—")
        self._cash_label = self._make_card("Cash", "—")
        self._total_account = self._make_card("Total Account", "—")
        for c in [self._total_label, self._cash_label, self._total_account]:
            cards_row.addWidget(c)
        cards_row.addStretch()
        root.addLayout(cards_row)

        # Positions table
        self._table = QTableWidget()
        cols = ["Ticker", "Shares", "Cost Basis", "Curr Price", "Value", "Gain/Loss", "Change%", "Target", "Stop"]
        self._table.setColumnCount(len(cols))
        self._table.setHorizontalHeaderLabels(cols)
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._table.setAlternatingRowColors(True)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        root.addWidget(self._table, stretch=1)

        # Remove button
        remove_row = QHBoxLayout()
        self._remove_btn = QPushButton("Remove Selected Position")
        self._remove_btn.setObjectName("danger")
        self._remove_btn.clicked.connect(self._remove_position)
        remove_row.addStretch()
        remove_row.addWidget(self._remove_btn)
        root.addLayout(remove_row)

        # Add position form
        add_box = QGroupBox("Add Position")
        form_vl = QVBoxLayout(add_box)
        form_vl.setContentsMargins(12, 14, 12, 12)
        form_vl.setSpacing(10)

        add_layout = QHBoxLayout()
        add_layout.setSpacing(10)

        self._f_ticker = QLineEdit()
        self._f_ticker.setPlaceholderText("Ticker")
        self._f_ticker.setMaximumWidth(100)

        self._f_shares = QDoubleSpinBox()
        self._f_shares.setRange(0.001, 1_000_000)
        self._f_shares.setDecimals(3)
        self._f_shares.setValue(1)
        self._f_shares.setPrefix("Shares: ")
        self._f_shares.setMaximumWidth(160)

        self._f_cost = QDoubleSpinBox()
        self._f_cost.setRange(0, 1_000_000)
        self._f_cost.setDecimals(2)
        self._f_cost.setPrefix("$ ")
        self._f_cost.setMaximumWidth(140)

        self._f_target = QDoubleSpinBox()
        self._f_target.setRange(0, 1_000_000)
        self._f_target.setDecimals(2)
        self._f_target.setPrefix("Target $")
        self._f_target.setMaximumWidth(150)

        self._f_stop = QDoubleSpinBox()
        self._f_stop.setRange(0, 1_000_000)
        self._f_stop.setDecimals(2)
        self._f_stop.setPrefix("Stop $")
        self._f_stop.setMaximumWidth(150)

        add_btn = QPushButton("Add")
        add_btn.setObjectName("primary")
        add_btn.setFixedWidth(80)
        add_btn.clicked.connect(self._add_position)

        for w in [self._f_ticker, self._f_shares, self._f_cost, self._f_target, self._f_stop, add_btn]:
            add_layout.addWidget(w)

        # Cash row inside the same box
        cash_row = QHBoxLayout()
        cash_row.addWidget(QLabel("Cash balance:"))
        self._cash_input = QDoubleSpinBox()
        self._cash_input.setRange(0, 100_000_000)
        self._cash_input.setDecimals(2)
        self._cash_input.setPrefix("$ ")
        self._cash_input.setMaximumWidth(160)
        save_cash_btn = QPushButton("Save Cash")
        save_cash_btn.setFixedWidth(100)
        save_cash_btn.clicked.connect(self._save_cash)
        cash_row.addWidget(self._cash_input)
        cash_row.addWidget(save_cash_btn)
        cash_row.addStretch()

        form_vl.addLayout(add_layout)
        form_vl.addLayout(cash_row)
        root.addWidget(add_box)

        self._load_portfolio()

    def _make_card(self, title, value):
        from PyQt6.QtWidgets import QFrame
        f = QFrame()
        f.setStyleSheet(
            "QFrame{background:#0a1020;border:1px solid #1e293b;border-radius:8px;padding:4px;}"
        )
        layout = QVBoxLayout(f)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(2)
        lbl = QLabel(title.upper())
        lbl.setStyleSheet("font-size:10px;color:#475569;font-weight:700;letter-spacing:1px;background:transparent;border:none;")
        val = QLabel(value)
        val.setStyleSheet("font-size:18px;font-weight:700;color:#EEF2FF;background:transparent;border:none;")
        layout.addWidget(lbl)
        layout.addWidget(val)
        f._val_label = val
        return f

    def _load_portfolio(self):
        from utils.config import load_portfolio
        port = load_portfolio()
        self._cash_input.setValue(port.get("cash", 0.0))
        self._populate_table(port.get("positions", []))

    def _populate_table(self, positions, enriched=False):
        self._table.setRowCount(len(positions))
        total_value = 0.0

        for i, pos in enumerate(positions):
            ticker = pos.get("ticker", "")
            shares = pos.get("shares", 0)
            cost = pos.get("cost_basis", 0)
            curr = pos.get("current_price", None)
            value = pos.get("value", None)
            gain = pos.get("gain_loss", None)
            change_pct = pos.get("change_pct", None)
            target = pos.get("target", None)
            stop = pos.get("stop", None)

            if value:
                total_value += value

            cells = [
                ticker,
                f"{shares:.3f}",
                f"${cost:.2f}" if cost else "—",
                f"${curr:.2f}" if curr else "—",
                f"${value:.2f}" if value else "—",
                (f"+${gain:.2f}" if gain and gain >= 0 else f"-${abs(gain):.2f}") if gain is not None else "—",
                (f"+{change_pct:.2f}%" if change_pct and change_pct >= 0 else f"{change_pct:.2f}%") if change_pct is not None else "—",
                f"${target:.2f}" if target else "—",
                f"${stop:.2f}" if stop else "—",
            ]

            for j, cell_text in enumerate(cells):
                item = QTableWidgetItem(cell_text)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if j == 5 and gain is not None:
                    item.setForeground(QColor("#10B981") if gain >= 0 else QColor("#F43F5E"))
                if j == 6 and change_pct is not None:
                    item.setForeground(QColor("#10B981") if change_pct >= 0 else QColor("#F43F5E"))
                self._table.setItem(i, j, item)

        from utils.config import load_portfolio
        port = load_portfolio()
        cash = port.get("cash", 0.0)
        self._total_label._val_label.setText(f"${total_value:,.2f}")
        self._cash_label._val_label.setText(f"${cash:,.2f}")
        self._total_account._val_label.setText(f"${total_value + cash:,.2f}")

    def _refresh(self):
        from utils.config import load_portfolio
        port = load_portfolio()
        positions = port.get("positions", [])
        if not positions:
            return
        self._refresh_btn.setEnabled(False)
        self._refresh_btn.setText("Refreshing…")

        from workers.market_worker import PortfolioWorker
        self._worker = PortfolioWorker(positions)
        self._worker.result.connect(lambda d: self._populate_table(d.get("positions", [])))
        self._worker.error.connect(lambda e: None)
        self._worker.finished.connect(lambda: (
            self._refresh_btn.setEnabled(True),
            self._refresh_btn.setText("Refresh Prices"),
        ))
        self._worker.start()

    def _add_position(self):
        ticker = self._f_ticker.text().strip().upper()
        shares = self._f_shares.value()
        cost = self._f_cost.value()
        if not ticker or shares <= 0:
            return

        from utils.config import load_portfolio, save_portfolio
        port = load_portfolio()
        pos = {"ticker": ticker, "shares": shares, "cost_basis": cost}
        if self._f_target.value() > 0:
            pos["target"] = self._f_target.value()
        if self._f_stop.value() > 0:
            pos["stop"] = self._f_stop.value()
        port["positions"].append(pos)
        save_portfolio(port)

        self._f_ticker.clear()
        self._f_shares.setValue(1)
        self._f_cost.setValue(0)
        self._f_target.setValue(0)
        self._f_stop.setValue(0)
        self._load_portfolio()
        self.portfolio_changed.emit()

    def _remove_position(self):
        row = self._table.currentRow()
        if row < 0:
            return
        ticker_item = self._table.item(row, 0)
        if not ticker_item:
            return
        ticker = ticker_item.text()
        reply = QMessageBox.question(
            self, "Remove Position",
            f"Remove {ticker} from portfolio?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        from utils.config import load_portfolio, save_portfolio
        port = load_portfolio()
        port["positions"] = [p for p in port["positions"] if p["ticker"] != ticker]
        save_portfolio(port)
        self._load_portfolio()
        self.portfolio_changed.emit()

    def _save_cash(self):
        from utils.config import load_portfolio, save_portfolio
        port = load_portfolio()
        port["cash"] = self._cash_input.value()
        save_portfolio(port)
        self._load_portfolio()
        self.portfolio_changed.emit()
