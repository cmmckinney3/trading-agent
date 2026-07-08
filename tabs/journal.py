from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTableWidget, QTableWidgetItem, QGroupBox,
    QDoubleSpinBox, QComboBox, QTextEdit, QHeaderView,
    QMessageBox, QTabWidget,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor


class JournalTab(QWidget):
    def __init__(self):
        super().__init__()
        self._alert_worker = None
        self._setup_ui()
        self._load()

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(10)

        # Header
        header_row = QHBoxLayout()
        title = QLabel("Trade Journal")
        title.setStyleSheet("font-size:18px;font-weight:700;color:#EEF2FF;")
        self._alert_btn = QPushButton("Check Alerts")
        self._alert_btn.setObjectName("primary")
        self._alert_btn.setFixedWidth(130)
        self._alert_btn.clicked.connect(self._check_alerts)
        header_row.addWidget(title)
        header_row.addStretch()
        header_row.addWidget(self._alert_btn)
        root.addLayout(header_row)

        self._alert_label = QLabel("")
        self._alert_label.setWordWrap(True)
        self._alert_label.setStyleSheet("font-size:13px;")
        root.addWidget(self._alert_label)

        # Log new trade
        log_box = QGroupBox("Log New Trade")
        log_layout = QHBoxLayout(log_box)
        log_layout.setSpacing(10)

        self._j_ticker = QLineEdit()
        self._j_ticker.setPlaceholderText("Ticker")
        self._j_ticker.setMaximumWidth(90)

        self._j_action = QComboBox()
        for a in ["BUY", "SELL", "SHORT"]:
            self._j_action.addItem(a)
        self._j_action.setMaximumWidth(90)

        self._j_entry = QDoubleSpinBox()
        self._j_entry.setRange(0, 1_000_000)
        self._j_entry.setDecimals(2)
        self._j_entry.setPrefix("Entry $")
        self._j_entry.setMaximumWidth(150)

        self._j_target = QDoubleSpinBox()
        self._j_target.setRange(0, 1_000_000)
        self._j_target.setDecimals(2)
        self._j_target.setPrefix("Target $")
        self._j_target.setMaximumWidth(150)

        self._j_stop = QDoubleSpinBox()
        self._j_stop.setRange(0, 1_000_000)
        self._j_stop.setDecimals(2)
        self._j_stop.setPrefix("Stop $")
        self._j_stop.setMaximumWidth(150)

        self._j_notes = QLineEdit()
        self._j_notes.setPlaceholderText("Notes / thesis")

        log_btn = QPushButton("Log")
        log_btn.setObjectName("primary")
        log_btn.setFixedWidth(70)
        log_btn.clicked.connect(self._log_trade)

        for w in [self._j_ticker, self._j_action, self._j_entry, self._j_target, self._j_stop, self._j_notes, log_btn]:
            log_layout.addWidget(w)
        root.addWidget(log_box)

        # Inner tab: open / closed
        inner_tabs = QTabWidget()
        inner_tabs.setStyleSheet("QTabBar::tab { min-width: 80px; padding: 6px 16px; }")

        # Open trades
        open_widget = QWidget()
        open_layout = QVBoxLayout(open_widget)
        open_layout.setContentsMargins(0, 8, 0, 0)
        self._open_table = self._make_table(
            ["ID", "Date", "Ticker", "Action", "Entry", "Target", "Stop", "Notes", "Close"]
        )
        open_layout.addWidget(self._open_table)
        inner_tabs.addTab(open_widget, "Open Trades")

        # Closed trades
        closed_widget = QWidget()
        closed_layout = QVBoxLayout(closed_widget)
        closed_layout.setContentsMargins(0, 8, 0, 0)
        self._closed_table = self._make_table(
            ["ID", "Ticker", "Action", "Entry", "Exit", "P&L %", "Exit Date", "Notes"]
        )
        closed_layout.addWidget(self._closed_table)
        inner_tabs.addTab(closed_widget, "Closed Trades")

        root.addWidget(inner_tabs, stretch=1)

    def _make_table(self, cols):
        t = QTableWidget()
        t.setColumnCount(len(cols))
        t.setHorizontalHeaderLabels(cols)
        t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        t.horizontalHeader().setStretchLastSection(True)
        t.setAlternatingRowColors(True)
        t.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        t.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        return t

    def _load(self):
        from utils.journal import load_journal
        journal = load_journal()
        open_trades = [t for t in journal if t["status"] == "open"]
        closed_trades = [t for t in journal if t["status"] == "closed"]
        self._populate_open(open_trades)
        self._populate_closed(closed_trades)

    def _populate_open(self, trades):
        self._open_table.setRowCount(len(trades))
        for i, t in enumerate(trades):
            cells = [
                str(t["id"]),
                t["logged_at"][:10],
                t["ticker"],
                t["action"],
                f"${t['entry_price']:.2f}",
                f"${t['target']:.2f}" if t.get("target") else "—",
                f"${t['stop']:.2f}" if t.get("stop") else "—",
                t.get("notes", "")[:40],
            ]
            for j, text in enumerate(cells):
                item = QTableWidgetItem(text)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self._open_table.setItem(i, j, item)

            close_btn = QPushButton("Close")
            close_btn.setObjectName("danger")
            close_btn.setFixedWidth(60)
            close_btn.clicked.connect(lambda _, tid=t["id"]: self._close_trade(tid))
            self._open_table.setCellWidget(i, 8, close_btn)

    def _populate_closed(self, trades):
        self._closed_table.setRowCount(len(trades))
        for i, t in enumerate(trades):
            pnl = t.get("pnl_pct")
            pnl_text = (f"+{pnl:.2f}%" if pnl >= 0 else f"{pnl:.2f}%") if pnl is not None else "—"
            cells = [
                str(t["id"]),
                t["ticker"],
                t["action"],
                f"${t['entry_price']:.2f}",
                f"${t['exit_price']:.2f}" if t.get("exit_price") else "—",
                pnl_text,
                (t.get("exit_date") or "")[:10],
                t.get("notes", "")[:40],
            ]
            for j, text in enumerate(cells):
                item = QTableWidgetItem(text)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if j == 5 and pnl is not None:
                    item.setForeground(QColor("#10B981") if pnl >= 0 else QColor("#F43F5E"))
                self._closed_table.setItem(i, j, item)

    def _log_trade(self):
        ticker = self._j_ticker.text().strip().upper()
        entry = self._j_entry.value()
        if not ticker or entry <= 0:
            QMessageBox.warning(self, "Missing Fields", "Enter a ticker and entry price.")
            return
        target = self._j_target.value() or None
        stop = self._j_stop.value() or None
        notes = self._j_notes.text().strip()

        from utils.journal import log_trade
        log_trade(ticker, self._j_action.currentText(), entry, target, stop, notes)

        self._j_ticker.clear()
        self._j_entry.setValue(0)
        self._j_target.setValue(0)
        self._j_stop.setValue(0)
        self._j_notes.clear()
        self._load()

    def _close_trade(self, trade_id):
        exit_price, ok = _get_double(self, "Close Trade", "Exit price:")
        if not ok or exit_price <= 0:
            return
        from utils.journal import close_trade
        close_trade(trade_id, exit_price)
        self._load()

    def _check_alerts(self):
        self._alert_btn.setEnabled(False)
        self._alert_btn.setText("Checking…")
        self._alert_label.setText("Checking open trade prices…")

        from PyQt6.QtCore import QThread, pyqtSignal

        class _AlertWorker(QThread):
            done = pyqtSignal(list)
            fail = pyqtSignal(str)

            def run(self):
                try:
                    from utils.journal import load_journal, check_alerts
                    self.done.emit(check_alerts(load_journal()))
                except Exception as e:
                    self.fail.emit(str(e))

        self._alert_worker = _AlertWorker()
        self._alert_worker.done.connect(self._on_alerts)
        self._alert_worker.fail.connect(lambda e: self._alert_label.setText(f"Error: {e}"))
        self._alert_worker.finished.connect(lambda: (
            self._alert_btn.setEnabled(True),
            self._alert_btn.setText("Check Alerts"),
        ))
        self._alert_worker.start()

    def _on_alerts(self, alerts):
        if not alerts:
            self._alert_label.setText("No alerts — all open trades within range.")
            self._alert_label.setStyleSheet("color:#10B981;font-size:13px;")
            return
        parts = []
        for a in alerts:
            t = a["trade"]
            if a["type"] == "TARGET_HIT":
                parts.append(
                    f"TARGET HIT: {t['ticker']} @ ${a['current_price']:.2f} >= target ${t['target']:.2f}"
                )
            else:
                parts.append(
                    f"STOP TRIGGERED: {t['ticker']} @ ${a['current_price']:.2f} <= stop ${t['stop']:.2f}"
                )
        self._alert_label.setText(" | ".join(parts))
        self._alert_label.setStyleSheet("color:#F59E0B;font-size:13px;font-weight:600;")


def _get_double(parent, title, label):
    from PyQt6.QtWidgets import QInputDialog
    return QInputDialog.getDouble(parent, title, label, 0.0, 0.0, 1_000_000, 2)
