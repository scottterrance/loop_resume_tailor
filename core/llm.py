"""
DeepSeek LLM client wrapper.
Provides a simple interface for chat completions with JSON mode support.
"""

import os
import json
import re
from openai import OpenAI

_clients = {}

def get_client(model_name: str) -> OpenAI:
    if model_name not in _clients:
        _clients[model_name] = OpenAI(
            api_key=os.environ.get("LLM_API_KEY", ""),
            base_url=os.environ.get("LLM_BASE_URL", "https://api.deepseek.com/v1"),
        )
    return _clients[model_name]

def chat(messages: list[dict], json_mode: bool = False, temperature: float = 0.3, model: str = None) -> str:
    """
    Send a chat completion request to DeepSeek.
    Returns the response content as a string.
    """
    model_to_use = model or os.environ.get("LLM_MODEL", "deepseek-chat")
    client = get_client(model_to_use)

    kwargs = {
        "model": model_to_use,
        "messages": messages,
        "temperature": temperature,
    }

    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    response = client.chat.completions.create(**kwargs)
    return response.choices[0].message.content

def chat_json(messages: list[dict], temperature: float = 0.2, model: str = None) -> dict:
    """
    Send a chat completion request and parse the response as JSON.
    """
    raw = chat(messages, json_mode=True, temperature=temperature, model=model)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Attempt to extract JSON from markdown code blocks
        match = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", raw)
        if match:
            return json.loads(match.group(1))
        raise ValueError(f"LLM returned non-JSON response: {raw[:200]}")
