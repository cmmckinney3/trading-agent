import os
from typing import Any, Dict, List, Optional


def chat_completions_create(
    *,
    model: str,
    messages: List[Dict[str, str]],
    temperature: float = 0.7,
    max_tokens: Optional[int] = None,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
) -> Dict[str, Any]:
    if not api_key:
        api_key = (
            os.getenv("OPENAI_API_KEY")
            or os.getenv("ALIBABA_API_KEY")
            or os.getenv("DASHSCOPE_API_KEY")
        )
    if not api_key:
        raise RuntimeError(
            "No API key configured. Go to the ⚙️ Settings tab to add your API key."
        )

    try:
        from openai import OpenAI
    except ImportError as e:
        raise RuntimeError(
            "Missing dependency 'openai'. Install it with: pip install openai"
        ) from e

    client_kwargs: Dict[str, Any] = {"api_key": api_key}
    if base_url:
        client_kwargs["base_url"] = base_url

    client = OpenAI(**client_kwargs)

    kwargs: Dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
    }
    if max_tokens is not None:
        kwargs["max_tokens"] = max_tokens

    resp = client.chat.completions.create(**kwargs)
    content = (resp.choices[0].message.content or "").strip()
    return {"content": content, "raw": resp}
