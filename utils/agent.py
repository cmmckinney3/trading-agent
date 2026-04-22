import json

from utils.llm import chat_completions_create
from utils.market_data import get_technicals, get_quote, screen_momentum_tickers

SYSTEM_PROMPT = """You are an aggressive swing trading analyst for a retail portfolio.
Your goal is to find high-probability, high-reward swing trades.

When giving trade recommendations, ALWAYS include:
1. **Action**: BUY / SELL / HOLD
2. **Ticker**: Symbol
3. **Entry Zone**: Price range to enter
4. **Target**: Price target (with % gain)
5. **Stop Loss**: Hard stop price (with % loss)
6. **Position Size**: Dollar amount and approx shares
7. **Timeframe**: Expected hold duration
8. **Thesis**: 2-3 sentence reasoning
9. **Risk/Reward**: Ratio

For position sizing:
- Max 40% of portfolio in any single trade
- Risk 5-8% of total portfolio per trade
- Size so the stop loss equals the max risk amount

You have access to real technical data. Be direct, confident, and actionable.
Format trade cards cleanly with clear sections. Use emojis sparingly."""


def _build_context(portfolio: dict, technicals: dict = None, screener_results: list = None) -> str:
    parts = []
    if portfolio:
        parts.append(f"CURRENT PORTFOLIO:\n{json.dumps(portfolio, indent=2)}")
    if technicals:
        parts.append(f"TECHNICAL DATA:\n{json.dumps(technicals, indent=2)}")
    if screener_results:
        parts.append(f"SCREENER RESULTS (top momentum plays):\n{json.dumps(screener_results, indent=2)}")
    return "\n\n".join(parts)


def _llm_kwargs(ai_config: dict) -> dict:
    return {
        "model": ai_config["model"],
        "api_key": ai_config.get("api_key") or None,
        "base_url": ai_config.get("base_url") or None,
    }


def chat_with_agent(
    user_message: str,
    conversation_history: list,
    portfolio: dict,
    ai_config: dict,
    technicals: dict = None,
    screener_results: list = None,
) -> str:
    context = _build_context(portfolio, technicals, screener_results)
    full_message = f"{context}\n\nUSER QUESTION: {user_message}" if context else user_message

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for msg in conversation_history:
        role = msg["role"] if msg["role"] in ["user", "assistant"] else "user"
        messages.append({"role": role, "content": msg["content"]})
    messages.append({"role": "user", "content": full_message})

    response = chat_completions_create(messages=messages, temperature=0.7, **_llm_kwargs(ai_config))
    return response["content"]


def get_trade_recommendation(ticker: str, portfolio: dict, ai_config: dict) -> str:
    tech = get_technicals(ticker)
    quote = get_quote(ticker)
    if not tech or not quote:
        return f"Could not fetch data for {ticker}. Please check the ticker symbol."

    context = _build_context(portfolio, tech)
    prompt = (
        f"{context}\n\nGenerate a detailed swing trade recommendation for {ticker} at "
        f"current price ${quote['price']}. Include all standard fields: action, entry zone, "
        f"target, stop loss, position size, timeframe, thesis, and risk/reward ratio."
    )

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]
    response = chat_completions_create(messages=messages, temperature=0.7, **_llm_kwargs(ai_config))
    return response["content"]


def run_daily_screener(portfolio: dict, ai_config: dict) -> str:
    screener_results = screen_momentum_tickers()
    if not screener_results:
        return "Screener returned no results. Market data may be unavailable."

    context = _build_context(portfolio, screener_results=screener_results)
    prompt = (
        f"{context}\n\nBased on the screener results above, give me your TOP 3 swing trade picks "
        f"for the next 2-5 days. For each pick provide the full trade card (entry, target, stop, "
        f"size, thesis). Also tell me if I should sell any existing positions to fund these trades."
    )

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]
    response = chat_completions_create(messages=messages, temperature=0.7, **_llm_kwargs(ai_config))
    return response["content"]
