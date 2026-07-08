import os
from typing import Any, Dict, List, Optional


def chat_completions_create(
    *,
    model: str,
    messages: List[Dict],
    temperature: float = 0.7,
    max_tokens: Optional[int] = None,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    tools: Optional[List[Dict]] = None,
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
    if tools:
        kwargs["tools"] = tools

    resp = client.chat.completions.create(**kwargs)
    choice = resp.choices[0]
    msg = choice.message
    content = (msg.content or "").strip()

    tool_calls = None
    tool_calls_raw = None
    if msg.tool_calls:
        tool_calls = [
            {"id": tc.id, "name": tc.function.name, "arguments": tc.function.arguments}
            for tc in msg.tool_calls
        ]
        tool_calls_raw = [
            {"id": tc.id, "type": "function", "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
            for tc in msg.tool_calls
        ]

    return {"content": content, "tool_calls": tool_calls, "tool_calls_raw": tool_calls_raw, "raw": resp}
