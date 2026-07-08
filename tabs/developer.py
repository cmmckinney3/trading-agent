from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)


class _ProjectScanWorker(QThread):
    done = pyqtSignal(object)
    fail = pyqtSignal(str)

    def __init__(self, path):
        super().__init__()
        self.path = path

    def run(self):
        try:
            from utils.personal_ops import scan_project
            self.done.emit(scan_project(self.path))
        except Exception as exc:
            self.fail.emit(str(exc))


class DeveloperTab(QWidget):
    def __init__(self):
        super().__init__()
        self._worker = None
        self._setup_ui()

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(12)

        header = QHBoxLayout()
        title = QLabel("Developer")
        title.setStyleSheet("font-size:18px;font-weight:700;color:#EEF2FF;")
        header.addWidget(title)
        header.addStretch()
        root.addLayout(header)

        input_box = QGroupBox("Project Scanner")
        input_layout = QVBoxLayout(input_box)
        input_layout.setContentsMargins(12, 14, 12, 12)

        row = QHBoxLayout()
        self._path = QLineEdit()
        self._path.setPlaceholderText("Project path. Leave blank for this app.")
        self._scan_btn = QPushButton("Scan")
        self._scan_btn.setObjectName("primary")
        self._scan_btn.setFixedWidth(90)
        self._scan_btn.clicked.connect(self._scan)
        row.addWidget(self._path)
        row.addWidget(self._scan_btn)
        input_layout.addLayout(row)

        self._hint = QLabel("Sensitive files like .env, credentials.json, and token files are skipped.")
        self._hint.setStyleSheet("color:#64748b;font-size:12px;")
        input_layout.addWidget(self._hint)
        root.addWidget(input_box)

        result_box = QGroupBox("Scan Results")
        result_layout = QVBoxLayout(result_box)
        result_layout.setContentsMargins(12, 14, 12, 12)
        self._results = QTextBrowser()
        self._results.setPlainText("No scan yet.")
        result_layout.addWidget(self._results)
        root.addWidget(result_box, stretch=1)

    def _scan(self):
        if self._worker is not None:
            return
        self._scan_btn.setEnabled(False)
        self._scan_btn.setText("Scanning...")
        self._results.setPlainText("Scanning project...")
        self._worker = _ProjectScanWorker(self._path.text().strip() or None)
        self._worker.done.connect(self._on_done)
        self._worker.fail.connect(self._on_fail)
        self._worker.finished.connect(self._on_finished)
        self._worker.start()

    def _on_done(self, data):
        if data.get("error"):
            self._results.setPlainText(data["error"])
            return
        ext_lines = "\n".join(f"- {ext}: {count}" for ext, count in data.get("top_extensions", []))
        todo_lines = "\n".join(
            f"- {item['file']}:{item['line']}  {item['text']}"
            for item in data.get("todos", [])
        ) or "- None found in sampled text files."
        file_lines = "\n".join(f"- {name}" for name in data.get("notable_files", [])[:40])

        self._results.setPlainText(
            f"Root: {data.get('root')}\n"
            f"Generated: {data.get('generated_at')}\n"
            f"Files sampled: {data.get('file_count_sampled')}\n"
            f"Estimated sampled size: {data.get('estimated_size_mb')} MB\n\n"
            f"Top extensions\n{ext_lines}\n\n"
            f"TODO / FIXME notes\n{todo_lines}\n\n"
            f"Notable files\n{file_lines}"
        )

    def _on_fail(self, message):
        self._results.setPlainText(f"Error: {message}")

    def _on_finished(self):
        self._worker = None
        self._scan_btn.setEnabled(True)
        self._scan_btn.setText("Scan")
