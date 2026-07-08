from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QTextBrowser, QTextEdit, QLabel,
)
from PyQt6.QtCore import Qt
import markdown as md_lib


def _render_md(text):
    body = md_lib.markdown(text or "", extensions=["tables", "fenced_code"])
    return f"""<html><head><style>
    body{{font-family:'Segoe UI',sans-serif;color:#EEF2FF;background:transparent;line-height:1.7;margin:0;padding:0;}}
    h1,h2,h3{{color:#c7d2fe;margin-top:10px;}}
    strong{{color:#a5b4fc;}}
    code{{background:#1e293b;padding:2px 6px;border-radius:3px;color:#22D3EE;font-family:monospace;font-size:12px;}}
    pre{{background:#0f1929;padding:10px;border-radius:6px;overflow-x:auto;margin:6px 0;}}
    table{{border-collapse:collapse;width:100%;margin:6px 0;}}
    th{{background:#0a1020;color:#94a3b8;padding:7px 10px;text-align:left;border-bottom:1px solid #1e293b;}}
    td{{padding:7px 10px;border-bottom:1px solid #0f1929;}}
    p{{margin:4px 0;}}
    </style></head><body>{body}</body></html>"""


_USER_BUBBLE = (
    "background:#1e293b;border-radius:10px 10px 2px 10px;"
    "padding:10px 14px;margin:4px 0;color:#EEF2FF;"
    "font-family:'Segoe UI',sans-serif;font-size:13px;line-height:1.6;"
)
_AI_BUBBLE = (
    "background:#0a1020;border:1px solid #1e293b;border-radius:10px 10px 10px 2px;"
    "padding:10px 14px;margin:4px 0;color:#EEF2FF;"
    "font-family:'Segoe UI',sans-serif;font-size:13px;line-height:1.6;"
)


class ChatTab(QWidget):
    def __init__(self):
        super().__init__()
        self._history = []
        self._worker = None
        self._setup_ui()

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(10)

        header_row = QHBoxLayout()
        title = QLabel("AI Chat")
        title.setStyleSheet("font-size:18px;font-weight:700;color:#EEF2FF;")
        caption = QLabel("The agent can call sysadmin, developer, weather, golf, and market tools.")
        caption.setStyleSheet("font-size:12px;color:#475569;")
        clear_btn = QPushButton("Clear")
        clear_btn.setFixedWidth(70)
        clear_btn.clicked.connect(self._clear)
        header_row.addWidget(title)
        header_row.addSpacing(12)
        header_row.addWidget(caption)
        header_row.addStretch()
        header_row.addWidget(clear_btn)
        root.addLayout(header_row)

        # Chat history
        self._history_browser = QTextBrowser()
        self._history_browser.setOpenExternalLinks(True)
        self._history_browser.document().setDefaultStyleSheet(
            "body{background:#070d1a;color:#EEF2FF;font-family:'Segoe UI',sans-serif;}"
        )
        root.addWidget(self._history_browser, stretch=1)

        # Input row
        input_row = QHBoxLayout()
        self._input = QTextEdit()
        self._input.setPlaceholderText("Ask about your machine, code, weather, golf window, market, or day...")
        self._input.setMaximumHeight(80)
        self._input.installEventFilter(self)

        self._send_btn = QPushButton("Send")
        self._send_btn.setObjectName("primary")
        self._send_btn.setFixedWidth(80)
        self._send_btn.setFixedHeight(80)
        self._send_btn.clicked.connect(self._send)

        input_row.addWidget(self._input)
        input_row.addWidget(self._send_btn)
        root.addLayout(input_row)

        self._status = QLabel("")
        self._status.setStyleSheet("color:#475569;font-size:12px;")
        root.addWidget(self._status)

    def eventFilter(self, obj, event):
        from PyQt6.QtCore import QEvent
        from PyQt6.QtGui import QKeyEvent
        if obj is self._input and event.type() == QEvent.Type.KeyPress:
            if (event.key() == Qt.Key.Key_Return and
                    not (event.modifiers() & Qt.KeyboardModifier.ShiftModifier)):
                self._send()
                return True
        return super().eventFilter(obj, event)

    def _send(self):
        text = self._input.toPlainText().strip()
        if not text or self._worker is not None:
            return

        from utils.config import load_config, load_portfolio
        config = load_config()
        if not config.get("api_key"):
            self._append_message("system", "No API key configured — go to Settings.")
            return

        self._input.clear()
        self._append_message("user", text)
        self._history.append({"role": "user", "content": text})

        self._send_btn.setEnabled(False)
        self._status.setText("Agent is thinking…")

        portfolio = load_portfolio()
        watchlist = config.get("watchlist")

        from workers.llm_worker import ChatWorker
        self._worker = ChatWorker(text, self._history[:-1], portfolio, config, watchlist)
        self._worker.result.connect(self._on_response)
        self._worker.error.connect(self._on_error)
        self._worker.finished.connect(self._on_done)
        self._worker.start()

    def _on_response(self, text):
        self._history.append({"role": "assistant", "content": text})
        self._append_message("assistant", text)

    def _on_error(self, msg):
        self._append_message("system", f"Error: {msg}")

    def _on_done(self):
        self._worker = None
        self._send_btn.setEnabled(True)
        self._status.setText("")

    def _append_message(self, role, text):
        doc = self._history_browser
        cursor = doc.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)

        if role == "user":
            html = (
                f"<div style='text-align:right;margin:6px 0'>"
                f"<span style='{_USER_BUBBLE}'>{text}</span></div>"
            )
            doc.insertHtml(html)
        elif role == "assistant":
            md_html = _render_md(text)
            inner = md_html[md_html.find("<body>") + 6:md_html.find("</body>")]
            html = f"<div style='{_AI_BUBBLE}'>{inner}</div><br>"
            doc.insertHtml(html)
        else:
            doc.insertHtml(
                f"<div style='color:#F59E0B;font-size:12px;margin:4px 0;padding:6px'>{text}</div>"
            )

        vbar = doc.verticalScrollBar()
        vbar.setValue(vbar.maximum())

    def _clear(self):
        self._history.clear()
        self._history_browser.clear()
