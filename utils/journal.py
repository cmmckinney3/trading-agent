import json
import os
from datetime import datetime

JOURNAL_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "trades.json")


def load_journal() -> list:
    if os.path.exists(JOURNAL_FILE):
        try:
            with open(JOURNAL_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return []


def _save_journal(journal: list) -> None:
    with open(JOURNAL_FILE, "w") as f:
        json.dump(journal, f, indent=2)


def log_trade(ticker: str, action: str, entry_price: float, target: float | None, stop: float | None, notes: str = "") -> dict:
    journal = load_journal()
    trade = {
        "id": max((t["id"] for t in journal), default=0) + 1,
        "logged_at": datetime.now().isoformat(),
        "ticker": ticker.upper(),
        "action": action.upper(),
        "entry_price": entry_price,
        "target": target,
        "stop": stop,
        "notes": notes,
        "status": "open",
        "exit_price": None,
        "exit_date": None,
        "pnl_pct": None,
    }
    journal.append(trade)
    _save_journal(journal)
    return trade


def close_trade(trade_id: int, exit_price: float) -> dict | None:
    journal = load_journal()
    for trade in journal:
        if trade["id"] == trade_id:
            trade["status"] = "closed"
            trade["exit_price"] = exit_price
            trade["exit_date"] = datetime.now().isoformat()
            if trade["entry_price"]:
                mult = 1 if trade["action"] in ("BUY", "LONG") else -1
                trade["pnl_pct"] = round(mult * (exit_price - trade["entry_price"]) / trade["entry_price"] * 100, 2)
            _save_journal(journal)
            return trade
    return None


def check_alerts(journal: list) -> list:
    """Return alert dicts for open trades where current price hit target or stop."""
    from utils.market_data import get_quote
    alerts = []
    for trade in journal:
        if trade["status"] != "open":
            continue
        quote = get_quote(trade["ticker"])
        if not quote:
            continue
        price = quote["price"]
        if trade.get("target") and price >= trade["target"]:
            alerts.append({"trade": trade, "type": "TARGET_HIT", "current_price": price})
        elif trade.get("stop") and price <= trade["stop"]:
            alerts.append({"trade": trade, "type": "STOP_HIT", "current_price": price})
    return alerts
