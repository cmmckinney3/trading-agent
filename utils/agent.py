import json

from utils.llm import chat_completions_create
from utils.market_data import get_technicals, get_quote, screen_momentum_tickers, get_news, get_earnings_date
from utils.personal_ops import get_system_snapshot, scan_project, get_golf_weather, build_daily_context

SYSTEM_PROMPT = """You are a local personal operations agent for a system administrator, developer, golfer, weather enthusiast, and hobby trader.
Your job is to be genuinely useful: gather local context, inspect available data, explain what matters, and recommend practical next actions.

Core modes:
- Sysadmin: summarize machine health, event log risks, storage pressure, processes, services, and safe diagnostic next steps.
- Developer: scan projects, identify TODOs, explain codebase shape, suggest tests and maintenance work.
- Weather/Golf: evaluate current weather, wind, humidity, UV, and golf playability.
- Trading: when asked, provide direct swing-trade analysis using live market tools.

For sysadmin and developer answers:
- Prefer evidence from tools over guesses.
- Separate observations, risk, and next actions.
- Do not suggest destructive commands unless the user explicitly asks.
- Flag secrets, tokens, and credentials as sensitive and avoid printing them.

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

You have access to real technical data and can call tools to fetch live market data.
Be direct, useful, and actionable. Format answers cleanly with clear sections."""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_technicals",
            "description": "Get technical indicators (RSI, MACD, Bollinger Bands, SMA20, SMA50, EMA9, ATR, volume ratio) for a stock ticker",
            "parameters": {
                "type": "object",
                "properties": {
                    "ticker": {"type": "string", "description": "Stock ticker symbol (e.g. NVDA, AAPL)"}
                },
                "required": ["ticker"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_quote",
            "description": "Get current price, daily change, and volume for a stock ticker",
            "parameters": {
                "type": "object",
                "properties": {
                    "ticker": {"type": "string", "description": "Stock ticker symbol"}
                },
                "required": ["ticker"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_news",
            "description": "Get recent news headlines for a stock ticker",
            "parameters": {
                "type": "object",
                "properties": {
                    "ticker": {"type": "string", "description": "Stock ticker symbol"}
                },
                "required": ["ticker"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_earnings_date",
            "description": "Get the next expected earnings date for a stock ticker",
            "parameters": {
                "type": "object",
                "properties": {
                    "ticker": {"type": "string", "description": "Stock ticker symbol"}
                },
                "required": ["ticker"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "screen_momentum",
            "description": "Screen the watchlist for high-momentum swing trade candidates, scored by RSI, volume, trend, and MACD",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_system_snapshot",
            "description": "Get read-only local Windows/system health details: disk, platform, boot time, top processes, stopped services, and recent System event errors",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "scan_project",
            "description": "Scan a local code project for structure, file types, notable files, and TODO/FIXME notes without reading secret files",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Optional absolute or relative project path. Omit to scan the current app project.",
                    }
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_golf_weather",
            "description": "Get current weather and a golf playability score for a city",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "City or location, e.g. Raleigh or Chicago"}
                },
                "required": ["city"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "build_daily_context",
            "description": "Build a personal daily context bundle combining system health, project scan, and optional golf/weather conditions",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "Optional city for weather/golf context"},
                    "project_path": {"type": "string", "description": "Optional project path to scan"},
                },
                "required": [],
            },
        },
    },
]


def _execute_tool(name: str, args: dict, watchlist: list = None):
    if name == "get_technicals":
        return get_technicals(args["ticker"])
    if name == "get_quote":
        return get_quote(args["ticker"])
    if name == "get_news":
        return get_news(args["ticker"])
    if name == "get_earnings_date":
        return get_earnings_date(args["ticker"])
    if name == "screen_momentum":
        return screen_momentum_tickers(watchlist=watchlist)
    if name == "get_system_snapshot":
        return get_system_snapshot()
    if name == "scan_project":
        return scan_project(args.get("path"))
    if name == "get_golf_weather":
        return get_golf_weather(args["city"])
    if name == "build_daily_context":
        return build_daily_context(args.get("city"), args.get("project_path"))
    return {"error": f"Unknown tool: {name}"}


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


def chat_with_agent_tools(
    user_message: str,
    conversation_history: list,
    portfolio: dict,
    ai_config: dict,
    watchlist: list = None,
) -> str:
    """Agentic chat that can call market data tools autonomously. Falls back to regular chat if provider doesn't support tool use."""
    context = _build_context(portfolio)
    full_message = f"{context}\n\nUSER QUESTION: {user_message}" if context else user_message

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for msg in conversation_history:
        role = msg["role"] if msg["role"] in ["user", "assistant"] else "user"
        messages.append({"role": role, "content": msg["content"]})
    messages.append({"role": "user", "content": full_message})

    try:
        for _ in range(6):
            response = chat_completions_create(
                messages=messages,
                temperature=0.7,
                tools=TOOLS,
                **_llm_kwargs(ai_config),
            )
            if not response.get("tool_calls"):
                return response["content"]

            messages.append({
                "role": "assistant",
                "content": response.get("content") or None,
                "tool_calls": response["tool_calls_raw"],
            })
            for tc in response["tool_calls"]:
                result = _execute_tool(tc["name"], json.loads(tc["arguments"]), watchlist)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": json.dumps(result, default=str),
                })

        return response.get("content") or "Analysis complete."

    except Exception:
        # Provider doesn't support tool use — fall back to regular completion
        return chat_with_agent(user_message, conversation_history, portfolio, ai_config)


def get_trade_recommendation(ticker: str, portfolio: dict, ai_config: dict) -> str:
    tech = get_technicals(ticker)
    quote = get_quote(ticker)
    if not tech or not quote:
        return f"Could not fetch data for {ticker}. Please check the ticker symbol."

    news = get_news(ticker, limit=5)
    earnings = get_earnings_date(ticker)

    context = _build_context(portfolio, tech)

    earnings_note = f"\nNOTE: Earnings expected on {earnings}. Factor this into timeframe and risk." if earnings else ""
    news_ctx = ""
    if news:
        headlines = "\n".join([f"- {n['date']} [{n['publisher']}] {n['title']}" for n in news])
        news_ctx = f"\nRECENT NEWS:\n{headlines}"

    prompt = (
        f"{context}{earnings_note}{news_ctx}\n\nGenerate a detailed swing trade recommendation for {ticker} at "
        f"current price ${quote['price']}. Include all standard fields: action, entry zone, "
        f"target, stop loss, position size, timeframe, thesis, and risk/reward ratio."
    )

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]
    response = chat_completions_create(messages=messages, temperature=0.7, **_llm_kwargs(ai_config))
    return response["content"]


def run_daily_screener(portfolio: dict, ai_config: dict, watchlist: list = None) -> str:
    screener_results = screen_momentum_tickers(watchlist=watchlist)
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
