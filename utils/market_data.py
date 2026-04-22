import yfinance as yf
import pandas as pd
import ta
import numpy as np
from datetime import datetime, timedelta


def get_quote(ticker: str) -> dict:
    """Get current quote for a ticker."""
    try:
        t = yf.Ticker(ticker)
        hist = t.history(period="2d")
        if hist.empty:
            return None
        current = hist["Close"].iloc[-1]
        prev = hist["Close"].iloc[-2] if len(hist) > 1 else current
        change = current - prev
        change_pct = (change / prev) * 100
        return {
            "ticker": ticker.upper(),
            "price": round(float(current), 2),
            "change": round(float(change), 2),
            "change_pct": round(float(change_pct), 2),
            "volume": int(hist["Volume"].iloc[-1]),
        }
    except Exception:
        return None


def get_technicals(ticker: str, period: str = "3mo") -> dict:
    """Get technical indicators for a ticker."""
    try:
        t = yf.Ticker(ticker)
        hist = t.history(period=period)
        if hist.empty or len(hist) < 20:
            return None

        df = hist.copy()
        close = df["Close"]
        high = df["High"]
        low = df["Low"]
        volume = df["Volume"]

        df["sma20"] = ta.trend.sma_indicator(close, window=20)
        df["sma50"] = ta.trend.sma_indicator(close, window=50)
        df["ema9"] = ta.trend.ema_indicator(close, window=9)
        df["rsi"] = ta.momentum.rsi(close, window=14)

        macd_obj = ta.trend.MACD(close)
        df["macd"] = macd_obj.macd()
        df["macd_signal"] = macd_obj.macd_signal()
        df["macd_hist"] = macd_obj.macd_diff()

        bb_obj = ta.volatility.BollingerBands(close, window=20)
        df["bb_upper"] = bb_obj.bollinger_hband()
        df["bb_lower"] = bb_obj.bollinger_lband()

        df["atr"] = ta.volatility.average_true_range(high, low, close, window=14)
        df["vol_sma20"] = ta.trend.sma_indicator(volume.astype(float), window=20)

        latest = df.iloc[-1]
        prev = df.iloc[-2]

        def safe(val):
            try:
                return None if pd.isna(val) else float(val)
            except Exception:
                return None

        vol_ratio = None
        vsma = safe(latest["vol_sma20"])
        if vsma and vsma > 0:
            vol_ratio = round(float(latest["Volume"]) / vsma, 2)

        macd_bullish = None
        mh_now = safe(latest["macd_hist"])
        mh_prev = safe(prev["macd_hist"])
        if mh_now is not None and mh_prev is not None:
            macd_bullish = mh_now > 0 and mh_prev <= 0

        return {
            "ticker": ticker.upper(),
            "price": round(float(latest["Close"]), 2),
            "sma20": round(safe(latest["sma20"]), 2) if safe(latest["sma20"]) else None,
            "sma50": round(safe(latest["sma50"]), 2) if safe(latest["sma50"]) else None,
            "ema9": round(safe(latest["ema9"]), 2) if safe(latest["ema9"]) else None,
            "rsi": round(safe(latest["rsi"]), 1) if safe(latest["rsi"]) else None,
            "macd": round(safe(latest["macd"]), 4) if safe(latest["macd"]) else None,
            "macd_signal": round(safe(latest["macd_signal"]), 4) if safe(latest["macd_signal"]) else None,
            "macd_hist": round(safe(latest["macd_hist"]), 4) if safe(latest["macd_hist"]) else None,
            "bb_upper": round(safe(latest["bb_upper"]), 2) if safe(latest["bb_upper"]) else None,
            "bb_lower": round(safe(latest["bb_lower"]), 2) if safe(latest["bb_lower"]) else None,
            "atr": round(safe(latest["atr"]), 2) if safe(latest["atr"]) else None,
            "vol_ratio": vol_ratio,
            "above_sma20": float(latest["Close"]) > float(latest["sma20"]) if safe(latest["sma20"]) else None,
            "above_sma50": float(latest["Close"]) > float(latest["sma50"]) if safe(latest["sma50"]) else None,
            "macd_bullish": macd_bullish,
        }
    except Exception:
        return None


def get_portfolio_value(positions: list) -> dict:
    """Calculate current portfolio value."""
    total = 0
    enriched = []
    for pos in positions:
        quote = get_quote(pos["ticker"])
        if quote:
            value = pos["shares"] * quote["price"]
            cost_basis = pos.get("cost_basis", 0)
            total += value
            enriched.append({
                **pos,
                "current_price": quote["price"],
                "value": round(value, 2),
                "change_pct": quote["change_pct"],
                "gain_loss": round(value - (cost_basis * pos["shares"]), 2) if cost_basis else None,
            })
        else:
            enriched.append(pos)
    return {"positions": enriched, "total_value": round(total, 2)}


def screen_momentum_tickers() -> list:
    """Screen a watchlist of high-momentum candidates."""
    candidates = [
        "NVDA", "AMD", "TSLA", "MSTR", "PLTR", "SOFI", "COIN",
        "SMCI", "IONQ", "RKLB", "LUNR", "JOBY", "ACHR", "RIVN",
        "HOOD", "UPST", "AFRM", "SOUN", "BBAI", "RGTI",
        "SOXL", "TQQQ", "LABU", "FNGU"
    ]
    results = []
    for ticker in candidates:
        tech = get_technicals(ticker, period="1mo")
        if tech and tech["rsi"] and tech["vol_ratio"]:
            score = 0
            if 45 < tech["rsi"] < 70:
                score += 2
            if tech["vol_ratio"] and tech["vol_ratio"] > 1.5:
                score += 2
            if tech["above_sma20"]:
                score += 1
            if tech["above_sma50"]:
                score += 1
            if tech["macd_bullish"]:
                score += 2
            if score >= 4:
                results.append({**tech, "score": score})
    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:6]


def get_price_history(ticker: str, period: str = "3mo") -> pd.DataFrame:
    """Get OHLCV history for charting."""
    try:
        t = yf.Ticker(ticker)
        return t.history(period=period)
    except Exception:
        return pd.DataFrame()