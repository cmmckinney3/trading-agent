from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)


class _SystemWorker(QThread):
    done = pyqtSignal(object)
    fail = pyqtSignal(str)

    def run(self):
        try:
            from utils.personal_ops import get_system_snapshot
            self.done.emit(get_system_snapshot())
        except Exception as exc:
            self.fail.emit(str(exc))


class SysadminTab(QWidget):
    def __init__(self):
        super().__init__()
        self._worker = None
        self._setup_ui()

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(12)

        header = QHBoxLayout()
        title = QLabel("Sysadmin")
        title.setStyleSheet("font-size:18px;font-weight:700;color:#EEF2FF;")
        self._refresh_btn = QPushButton("Run Diagnostics")
        self._refresh_btn.setObjectName("primary")
        self._refresh_btn.setFixedWidth(140)
        self._refresh_btn.clicked.connect(self._refresh)
        header.addWidget(title)
        header.addStretch()
        header.addWidget(self._refresh_btn)
        root.addLayout(header)

        summary_box = QGroupBox("Machine Health")
        summary_layout = QVBoxLayout(summary_box)
        summary_layout.setContentsMargins(12, 14, 12, 12)
        self._summary = QLabel("Run diagnostics to inspect local machine health.")
        self._summary.setWordWrap(True)
        self._summary.setStyleSheet("color:#CBD5E1;font-size:13px;line-height:1.6;")
        summary_layout.addWidget(self._summary)
        root.addWidget(summary_box)

        detail_box = QGroupBox("Read-only Details")
        detail_layout = QVBoxLayout(detail_box)
        detail_layout.setContentsMargins(12, 14, 12, 12)
        self._details = QTextBrowser()
        self._details.setOpenExternalLinks(False)
        self._details.setPlainText("No diagnostics loaded.")
        detail_layout.addWidget(self._details)
        root.addWidget(detail_box, stretch=1)

    def _refresh(self):
        if self._worker is not None:
            return
        self._refresh_btn.setEnabled(False)
        self._refresh_btn.setText("Running...")
        self._summary.setText("Collecting disk, process, service, and event-log snapshots...")
        self._details.setPlainText("")
        self._worker = _SystemWorker()
        self._worker.done.connect(self._on_done)
        self._worker.fail.connect(self._on_fail)
        self._worker.finished.connect(self._on_finished)
        self._worker.start()

    def _on_done(self, data):
        disk = data.get("disk", {})
        self._summary.setText(
            f"{data.get('hostname')} on {data.get('platform')}\n"
            f"Disk: {disk.get('used_gb')} GB used of {disk.get('total_gb')} GB "
            f"({disk.get('used_pct')}%). Free: {disk.get('free_gb')} GB.\n"
            f"Generated: {data.get('generated_at')}"
        )
        self._details.setPlainText(
            "Boot time\n"
            f"{data.get('boot_time')}\n\n"
            "Top CPU processes\n"
            f"{data.get('top_processes')}\n\n"
            "Stopped services sample\n"
            f"{data.get('stopped_services_sample')}\n\n"
            "Recent System errors\n"
            f"{data.get('recent_system_errors')}"
        )

    def _on_fail(self, message):
        self._summary.setText(f"Error: {message}")

    def _on_finished(self):
        self._worker = None
        self._refresh_btn.setEnabled(True)
        self._refresh_btn.setText("Run Diagnostics")
