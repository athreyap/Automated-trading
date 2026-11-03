"""Provider adapters for AlphaFund's private/local and cloud language models."""
from __future__ import annotations

import requests


class AIProviderError(RuntimeError):
    pass


def ollama_chat(messages: list[dict], model: str = "qwen2.5:7b",
                base_url: str = "http://localhost:11434", timeout: int = 180) -> str:
    """Call an Ollama server. No portfolio data leaves the configured Ollama host."""
    url = base_url.rstrip("/") + "/api/chat"
    try:
        response = requests.post(
            url,
            json={"model": model, "messages": messages, "stream": False,
                  "options": {"temperature": 0.2}},
            timeout=timeout,
        )
        response.raise_for_status()
        payload = response.json()
        answer = (payload.get("message") or {}).get("content", "").strip()
        if not answer:
            raise AIProviderError("Ollama returned an empty response.")
        return answer
    except requests.RequestException as exc:
        raise AIProviderError(
            f"Cannot reach Ollama at {base_url}. Start Ollama and verify the model is installed."
        ) from exc


def openai_chat(messages: list[dict], api_key: str, model: str = "gpt-4o-mini") -> str:
    if not api_key:
        raise AIProviderError("OPENAI_API_KEY is not configured.")
    try:
        from openai import OpenAI
        response = OpenAI(api_key=api_key).chat.completions.create(
            model=model, temperature=0.2, messages=messages
        )
        answer = response.choices[0].message.content
        if not answer:
            raise AIProviderError("OpenAI returned an empty response.")
        return answer
    except Exception as exc:
        raise AIProviderError(f"OpenAI request failed ({type(exc).__name__}).") from exc
