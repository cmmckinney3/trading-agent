import json
import os

CONFIG_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.json")
PORTFOLIO_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "portfolio.json")

DEFAULT_PORTFOLIO = {"positions": [], "cash": 0.0}

PROVIDER_PRESETS = {
    "OpenAI": {
        "base_url": "https://api.openai.com/v1",
        "default_model": "gpt-4o-mini",
        "placeholder": "sk-...",
        "info": "Get your key at platform.openai.com. GPT-4o-mini is affordable and fast.",
    },
    "Alibaba DashScope": {
        "base_url": "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
        "default_model": "qwen-max",
        "placeholder": "sk-...",
        "info": "Get your key at dashscope.aliyuncs.com. Qwen models offer strong performance.",
    },
    "Groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "default_model": "llama-3.3-70b-versatile",
        "placeholder": "gsk_...",
        "info": "Get your key at console.groq.com. Very fast inference with a generous free tier.",
    },
    "LM Studio": {
        "base_url": "http://localhost:1234/v1",
        "default_model": "qwen3.6-27b",
        "placeholder": "lm-studio",
        "info": "Local LM Studio server (default port 1234). Use any non-empty string as the API key — LM Studio does not validate it. Make sure LM Studio is running and a model is loaded.",
    },
    "Custom (OpenAI-compatible)": {
        "base_url": "",
        "default_model": "",
        "placeholder": "your-api-key",
        "info": "Any OpenAI-compatible endpoint — Together AI, Mistral, Ollama, etc.",
    },
}

def load_portfolio() -> dict:
    if os.path.exists(PORTFOLIO_FILE):
        try:
            with open(PORTFOLIO_FILE, "r") as f:
                data = json.load(f)
            return {**DEFAULT_PORTFOLIO, **data}
        except Exception:
            pass
    return DEFAULT_PORTFOLIO.copy()


def save_portfolio(portfolio: dict) -> None:
    with open(PORTFOLIO_FILE, "w") as f:
        json.dump(portfolio, f, indent=2)


DEFAULT_WATCHLIST = [
    "NVDA", "AMD", "TSLA", "MSTR", "PLTR", "SOFI", "COIN",
    "SMCI", "IONQ", "RKLB", "LUNR", "JOBY", "ACHR", "RIVN",
    "HOOD", "UPST", "AFRM", "SOUN", "BBAI", "RGTI",
    "SOXL", "TQQQ", "LABU", "FNGU",
]

DEFAULT_CONFIG = {
    "provider": "OpenAI",
    "api_key": "",
    "base_url": "https://api.openai.com/v1",
    "model": "gpt-4o-mini",
    "city": "",
    "watchlist": DEFAULT_WATCHLIST,
}


def load_config() -> dict:
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                data = json.load(f)
            return {**DEFAULT_CONFIG, **data}
        except Exception:
            pass
    return DEFAULT_CONFIG.copy()


def save_config(config: dict) -> None:
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)
