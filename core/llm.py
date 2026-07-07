"""
DeepSeek LLM client wrapper.
Provides a simple interface for chat completions with JSON mode support.
"""

import os
import json
from openai import OpenAI

_client = None


def get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(
            api_key=os.environ.get("LLM_API_KEY", ""),
            base_url=os.environ.get("LLM_BASE_URL", "https://api.deepseek.com/v1"),
        )
    return _client


def chat(messages: list[dict], json_mode: bool = False, temperature: float = 0.3) -> str:
    """
    Send a chat completion request to DeepSeek.
    Returns the response content as a string.
    """
    client = get_client()
    model = os.environ.get("LLM_MODEL", "deepseek-chat")

    kwargs = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
    }

    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    response = client.chat.completions.create(**kwargs)
    return response.choices[0].message.content


def chat_json(messages: list[dict], temperature: float = 0.2) -> dict:
    """
    Send a chat completion request and parse the response as JSON.
    """
    raw = chat(messages, json_mode=True, temperature=temperature)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Attempt to extract JSON from markdown code blocks
        import re
        match = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", raw)
        if match:
            return json.loads(match.group(1))
        raise ValueError(f"LLM returned non-JSON response: {raw[:200]}")
