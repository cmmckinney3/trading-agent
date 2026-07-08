from PyQt6.QtCore import QThread, pyqtSignal


class AnalysisWorker(QThread):
    result = pyqtSignal(object)
    error = pyqtSignal(str)

    def __init__(self, ticker, period="3mo"):
        super().__init__()
        self.ticker = ticker
        self.period = period

    def run(self):
        try:
            from utils.market_data import get_quote, get_technicals, get_price_history, get_news, get_earnings_date
            self.result.emit({
                "quote": get_quote(self.ticker),
                "technicals": get_technicals(self.ticker, period=self.period),
                "history": get_price_history(self.ticker, period=self.period),
                "news": get_news(self.ticker, limit=5),
                "earnings": get_earnings_date(self.ticker),
            })
        except Exception as e:
            self.error.emit(str(e))


class PortfolioWorker(QThread):
    result = pyqtSignal(object)
    error = pyqtSignal(str)

    def __init__(self, positions):
        super().__init__()
        self.positions = positions

    def run(self):
        try:
            from utils.market_data import get_portfolio_value
            self.result.emit(get_portfolio_value(self.positions))
        except Exception as e:
            self.error.emit(str(e))


class ScreenerWorker(QThread):
    result = pyqtSignal(object)
    error = pyqtSignal(str)

    def __init__(self, watchlist=None):
        super().__init__()
        self.watchlist = watchlist

    def run(self):
        try:
            from utils.market_data import screen_momentum_tickers
            self.result.emit(screen_momentum_tickers(self.watchlist))
        except Exception as e:
            self.error.emit(str(e))


class WeatherWorker(QThread):
    result = pyqtSignal(object)
    error = pyqtSignal(str)

    def __init__(self, city):
        super().__init__()
        self.city = city

    def run(self):
        try:
            from utils.weather import get_weather
            self.result.emit(get_weather(self.city) or "Weather unavailable")
        except Exception as e:
            self.error.emit(str(e))
