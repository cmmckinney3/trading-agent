import os

from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)


TASK_PRESETS = {
    "Custom task": "",
    "Improve code quality and readability": (
        "Review the codebase and improve code quality and readability. Look for duplicated "
        "logic, unclear naming, dead code, and inconsistent patterns. Fix what you find."
    ),
    "Add error handling": (
        "Review the codebase and add robust error handling and input validation where it is "
        "missing or insufficient."
    ),
    "Refactor to reduce duplication": (
        "Find duplicated code and logic across the codebase and refactor it into shared helpers "
        "or utilities."
    ),
    "Add type hints": (
        "Add Python type hints to all functions and methods that are missing them, following "
        "the existing style."
    ),
    "Write a README": (
        "Create a comprehensive README.md for this project: overview, setup instructions, usage, "
        "and architecture."
    ),
    "Add logging": (
        "Add structured logging throughout the codebase using Python's logging module, replacing "
        "any bare print statements."
    ),
}


class _CodeAgentWorker(QThread):
    event = pyqtSignal(object)

    def __init__(self, task, path, config, max_rounds):
        super().__init__()
        self.task = task
        self.path = path
        self.config = config
        self.max_rounds = max_rounds

    def run(self):
        try:
            from utils.code_agent import run_code_agent

            for event in run_code_agent(
                self.task,
                self.path,
                self.config,
                max_rounds=self.max_rounds,
            ):
                self.event.emit(event)
        except Exception as exc:
            self.event.emit({"type": "error", "message": str(exc)})


class CodeAgentTab(QWidget):
    def __init__(self):
        super().__init__()
        self._worker = None
        self._changed_files = []
        self._setup_ui()

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(10)

        header = QHBoxLayout()
        title = QLabel("Code Agent")
        title.setStyleSheet("font-size:18px;font-weight:700;color:#EEF2FF;")
        caption = QLabel("Point the agent at a codebase and give it a task.")
        caption.setStyleSheet("font-size:12px;color:#475569;")
        header.addWidget(title)
        header.addSpacing(12)
        header.addWidget(caption)
        header.addStretch()
        root.addLayout(header)

        config_box = QGroupBox("Run Configuration")
        config_layout = QVBoxLayout(config_box)
        config_layout.setContentsMargins(12, 14, 12, 12)
        config_layout.setSpacing(10)

        path_row = QHBoxLayout()
        self._path = QLineEdit()
        self._path.setText(os.getcwd())
        self._path.setPlaceholderText("Codebase path")
        self._rounds = QSpinBox()
        self._rounds.setRange(1, 50)
        self._rounds.setValue(20)
        self._rounds.setPrefix("Max rounds: ")
        self._rounds.setMaximumWidth(150)
        path_row.addWidget(self._path, stretch=1)
        path_row.addWidget(self._rounds)
        config_layout.addLayout(path_row)

        self._preset = QComboBox()
        for name in TASK_PRESETS:
            self._preset.addItem(name)
        self._preset.currentTextChanged.connect(self._on_preset)
        config_layout.addWidget(self._preset)

        self._task = QPlainTextEdit()
        self._task.setPlaceholderText("Describe exactly what you want the agent to do...")
        self._task.setMaximumHeight(110)
        config_layout.addWidget(self._task)

        button_row = QHBoxLayout()
        self._run_btn = QPushButton("Run Agent")
        self._run_btn.setObjectName("primary")
        self._run_btn.setFixedWidth(120)
        self._run_btn.clicked.connect(self._run)
        self._status = QLabel("")
        self._status.setStyleSheet("color:#64748b;font-size:12px;")
        button_row.addWidget(self._run_btn)
        button_row.addWidget(self._status)
        button_row.addStretch()
        config_layout.addLayout(button_row)
        root.addWidget(config_box)

        output_box = QGroupBox("Agent Log")
        output_layout = QVBoxLayout(output_box)
        output_layout.setContentsMargins(12, 14, 12, 12)
        self._log = QTextBrowser()
        self._log.setOpenExternalLinks(False)
        self._log.setHtml(
            "<p style='color:#64748b;font-family:Segoe UI'>No run yet.</p>"
        )
        output_layout.addWidget(self._log)
        root.addWidget(output_box, stretch=1)

    def _on_preset(self, name):
        self._task.setPlainText(TASK_PRESETS.get(name, ""))

    def _run(self):
        if self._worker is not None:
            return

        task = self._task.toPlainText().strip()
        path = self._path.text().strip()
        if not task:
            self._status.setText("Enter a task description.")
            self._status.setStyleSheet("color:#F43F5E;font-size:12px;")
            return
        if not path:
            self._status.setText("Enter a codebase path.")
            self._status.setStyleSheet("color:#F43F5E;font-size:12px;")
            return

        from utils.config import load_config

        config = load_config()
        if not config.get("api_key"):
            self._status.setText("No API key configured. Go to Settings.")
            self._status.setStyleSheet("color:#F43F5E;font-size:12px;")
            return

        self._changed_files = []
        self._log.clear()
        self._append("<b>Agent running...</b>")
        self._run_btn.setEnabled(False)
        self._run_btn.setText("Running...")
        self._status.setText("")

        self._worker = _CodeAgentWorker(task, path, config, self._rounds.value())
        self._worker.event.connect(self._on_event)
        self._worker.finished.connect(self._on_finished)
        self._worker.start()

    def _on_event(self, event):
        etype = event.get("type")
        if etype == "round":
            self._append(
                f"<hr><b style='color:#a5b4fc'>Round {event['round']} / {event['max']}</b>"
            )
        elif etype == "thought":
            self._append_md(event.get("content", ""))
        elif etype == "tool_call":
            name = event.get("name")
            args = event.get("args", {})
            label = args.get("path") or args.get("directory") or ""
            if name == "list_files":
                label = f"{args.get('directory', '.')} / {args.get('pattern', '**/*')}"
            self._append(
                f"<span style='color:#22D3EE'>tool:</span> "
                f"<code>{name}</code> <span style='color:#64748b'>{label}</span>"
            )
        elif etype == "tool_result":
            result = event.get("result", {})
            if result.get("error"):
                self._append(
                    f"<span style='color:#F43F5E'>Tool error: {result['error']}</span>"
                )
        elif etype in ("done", "max_rounds"):
            self._changed_files = event.get("changed_files", [])
            if self._changed_files:
                files = "".join(f"<li><code>{f}</code></li>" for f in self._changed_files)
                self._append(f"<hr><b>Files changed</b><ul>{files}</ul>")
            summary = event.get("summary") or event.get("message") or ""
            if summary:
                self._append("<b>Summary</b>")
                self._append_md(summary)
            if etype == "max_rounds":
                self._status.setText("Stopped at max rounds.")
                self._status.setStyleSheet("color:#F59E0B;font-size:12px;")
        elif etype == "error":
            self._append(
                f"<span style='color:#F43F5E'>Error: {event.get('message', '')}</span>"
            )
            self._status.setText("Agent error.")
            self._status.setStyleSheet("color:#F43F5E;font-size:12px;")

    def _on_finished(self):
        self._worker = None
        self._run_btn.setEnabled(True)
        self._run_btn.setText("Run Agent")
        if not self._status.text():
            self._status.setText("Complete.")
            self._status.setStyleSheet("color:#10B981;font-size:12px;")

    def _append(self, html):
        self._log.append(
            f"<div style='font-family:Segoe UI;color:#EEF2FF;line-height:1.6'>{html}</div>"
        )
        self._log.verticalScrollBar().setValue(self._log.verticalScrollBar().maximum())

    def _append_md(self, text):
        import markdown as md_lib

        body = md_lib.markdown(text or "", extensions=["tables", "fenced_code"])
        self._append(body)
