from PyQt6.QtCore import QThread, pyqtSignal


class ChatWorker(QThread):
    result = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, message, history, portfolio, config, watchlist=None):
        super().__init__()
        self.message = message
        self.history = history
        self.portfolio = portfolio
        self.config = config
        self.watchlist = watchlist

    def run(self):
        try:
            from utils.agent import chat_with_agent_tools
            self.result.emit(
                chat_with_agent_tools(self.message, self.history, self.portfolio, self.config, self.watchlist)
            )
        except Exception as e:
            self.error.emit(str(e))


class RecommendationWorker(QThread):
    result = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, ticker, portfolio, config):
        super().__init__()
        self.ticker = ticker
        self.portfolio = portfolio
        self.config = config

    def run(self):
        try:
            from utils.agent import get_trade_recommendation
            self.result.emit(get_trade_recommendation(self.ticker, self.portfolio, self.config))
        except Exception as e:
            self.error.emit(str(e))


class ScreenerLLMWorker(QThread):
    result = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, portfolio, config, watchlist=None):
        super().__init__()
        self.portfolio = portfolio
        self.config = config
        self.watchlist = watchlist

    def run(self):
        try:
            from utils.agent import run_daily_screener
            self.result.emit(run_daily_screener(self.portfolio, self.config, self.watchlist))
        except Exception as e:
            self.error.emit(str(e))


class BriefingLLMWorker(QThread):
    result = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, portfolio, config):
        super().__init__()
        self.portfolio = portfolio
        self.config = config

    def run(self):
        try:
            import json
            from utils.agent import chat_with_agent
            from utils.personal_ops import build_daily_context
            city = self.config.get("city")
            context = build_daily_context(city=city)
            self.result.emit(
                chat_with_agent(
                    (
                        "Create a concise personal morning briefing from this context. "
                        "Cover schedule/email caveats if absent, local system health, developer maintenance items, "
                        "weather/golf conditions, and market/trading notes only if relevant. "
                        "End with 3-5 concrete priorities.\n\n"
                        f"CONTEXT:\n{json.dumps(context, indent=2, default=str)}"
                    ),
                    [], self.portfolio, self.config,
                )
            )
        except Exception as e:
            self.error.emit(str(e))
