from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QComboBox, QGroupBox, QPlainTextEdit,
    QFormLayout, QMessageBox,
)
from PyQt6.QtCore import Qt


class SettingsTab(QWidget):
    def __init__(self):
        super().__init__()
        self._setup_ui()
        self._load()

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(14)
        root.setAlignment(Qt.AlignmentFlag.AlignTop)

        title = QLabel("Settings")
        title.setStyleSheet("font-size:18px;font-weight:700;color:#EEF2FF;")
        root.addWidget(title)

        # LLM Config
        llm_box = QGroupBox("LLM Provider")
        form = QFormLayout(llm_box)
        form.setSpacing(10)
        form.setContentsMargins(16, 18, 16, 16)

        self._provider_combo = QComboBox()
        from utils.config import PROVIDER_PRESETS
        for name in PROVIDER_PRESETS:
            self._provider_combo.addItem(name)
        self._provider_combo.addItem("Custom (OpenAI-compatible)")
        self._provider_combo.currentTextChanged.connect(self._on_provider_change)

        self._model_input = QLineEdit()
        self._model_input.setPlaceholderText("e.g. gpt-4o-mini")

        self._apikey_input = QLineEdit()
        self._apikey_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._apikey_input.setPlaceholderText("API key")

        self._baseurl_input = QLineEdit()
        self._baseurl_input.setPlaceholderText("https://api.openai.com/v1")

        form.addRow("Provider:", self._provider_combo)
        form.addRow("Model:", self._model_input)
        form.addRow("API Key:", self._apikey_input)
        form.addRow("Base URL:", self._baseurl_input)

        self._provider_info = QLabel("")
        self._provider_info.setStyleSheet("color:#64748b;font-size:12px;")
        self._provider_info.setWordWrap(True)
        form.addRow("", self._provider_info)
        root.addWidget(llm_box)

        # General
        gen_box = QGroupBox("General")
        gen_form = QFormLayout(gen_box)
        gen_form.setSpacing(10)
        gen_form.setContentsMargins(16, 18, 16, 16)

        self._city_input = QLineEdit()
        self._city_input.setPlaceholderText("e.g. New York")
        gen_form.addRow("City (weather):", self._city_input)
        root.addWidget(gen_box)

        # Watchlist
        wl_box = QGroupBox("Screener Watchlist")
        wl_layout = QVBoxLayout(wl_box)
        wl_layout.setContentsMargins(16, 18, 16, 16)
        wl_layout.addWidget(QLabel("Comma-separated ticker symbols:"))
        self._watchlist_input = QPlainTextEdit()
        self._watchlist_input.setMaximumHeight(90)
        wl_layout.addWidget(self._watchlist_input)
        root.addWidget(wl_box)

        # Buttons
        btn_row = QHBoxLayout()
        self._save_btn = QPushButton("Save Settings")
        self._save_btn.setObjectName("primary")
        self._save_btn.setFixedWidth(140)
        self._save_btn.clicked.connect(self._save)

        self._test_btn = QPushButton("Test Connection")
        self._test_btn.setFixedWidth(140)
        self._test_btn.clicked.connect(self._test)

        self._status = QLabel("")
        self._status.setStyleSheet("font-size:13px;")

        btn_row.addWidget(self._save_btn)
        btn_row.addWidget(self._test_btn)
        btn_row.addWidget(self._status)
        btn_row.addStretch()
        root.addLayout(btn_row)

        root.addStretch()

    def _load(self):
        from utils.config import load_config, PROVIDER_PRESETS
        cfg = load_config()
        provider = cfg.get("provider", "OpenAI")
        idx = self._provider_combo.findText(provider)
        if idx >= 0:
            self._provider_combo.setCurrentIndex(idx)
        self._model_input.setText(cfg.get("model", ""))
        self._apikey_input.setText(cfg.get("api_key", ""))
        self._baseurl_input.setText(cfg.get("base_url", ""))
        self._city_input.setText(cfg.get("city", ""))
        wl = cfg.get("watchlist", [])
        self._watchlist_input.setPlainText(", ".join(wl))
        self._update_provider_info(provider)

    def _on_provider_change(self, provider):
        from utils.config import PROVIDER_PRESETS
        preset = PROVIDER_PRESETS.get(provider)
        if preset:
            self._baseurl_input.setText(preset.get("base_url", ""))
            self._model_input.setText(preset.get("default_model", ""))
            self._apikey_input.setPlaceholderText(preset.get("placeholder", ""))
        self._update_provider_info(provider)

    def _update_provider_info(self, provider):
        from utils.config import PROVIDER_PRESETS
        preset = PROVIDER_PRESETS.get(provider)
        if preset:
            self._provider_info.setText(preset.get("info", ""))
        else:
            self._provider_info.setText("")

    def _save(self):
        from utils.config import save_config, DEFAULT_WATCHLIST
        raw_wl = self._watchlist_input.toPlainText()
        watchlist = [t.strip().upper() for t in raw_wl.split(",") if t.strip()] or DEFAULT_WATCHLIST
        cfg = {
            "provider": self._provider_combo.currentText(),
            "api_key": self._apikey_input.text().strip(),
            "base_url": self._baseurl_input.text().strip(),
            "model": self._model_input.text().strip(),
            "city": self._city_input.text().strip(),
            "watchlist": watchlist,
        }
        save_config(cfg)
        self._status.setText("Saved.")
        self._status.setStyleSheet("color:#10B981;font-size:13px;")

    def _test(self):
        api_key = self._apikey_input.text().strip()
        model = self._model_input.text().strip()
        base_url = self._baseurl_input.text().strip() or None
        if not api_key:
            self._status.setText("Enter an API key first.")
            self._status.setStyleSheet("color:#F43F5E;font-size:13px;")
            return
        self._test_btn.setEnabled(False)
        self._test_btn.setText("Testing…")
        self._status.setText("")

        from PyQt6.QtCore import QThread, pyqtSignal

        class _TestWorker(QThread):
            ok = pyqtSignal(str)
            fail = pyqtSignal(str)

            def __init__(self, model, api_key, base_url):
                super().__init__()
                self.model = model
                self.api_key = api_key
                self.base_url = base_url

            def run(self):
                try:
                    from utils.llm import chat_completions_create
                    r = chat_completions_create(
                        model=self.model,
                        messages=[{"role": "user", "content": "Reply with exactly one word: OK"}],
                        temperature=0,
                        api_key=self.api_key,
                        base_url=self.base_url,
                    )
                    self.ok.emit(r.get("content", "")[:60])
                except Exception as e:
                    self.fail.emit(str(e)[:120])

        self._test_worker = _TestWorker(model, api_key, base_url)
        self._test_worker.ok.connect(lambda r: (
            self._status.setText(f"Connected! Reply: {r}"),
            self._status.setStyleSheet("color:#10B981;font-size:13px;"),
        ))
        self._test_worker.fail.connect(lambda e: (
            self._status.setText(f"Failed: {e}"),
            self._status.setStyleSheet("color:#F43F5E;font-size:12px;"),
        ))
        self._test_worker.finished.connect(lambda: (
            self._test_btn.setEnabled(True),
            self._test_btn.setText("Test Connection"),
        ))
        self._test_worker.start()
