"Provider adapters for AlphaFund's local and managed open-weight language models."
from __future__ import annotations

import requests


class AIProviderError(RuntimeError):
    """Raised when a configured inference provider cannot complete a request."""


def _openai_compatible_chat(messages: list[dict], api_key: str, model: str,
                            base_url: str, provider_name: str) -> str:
    if not api_key:
        raise AIProviderError(f"{provider_name} API token is not configured.")
    try:
        from openai import OpenAI
        response = OpenAI(api_key=api_key, base_url=base_url, timeout=90.0).chat.completions.create(
            model=model, temperature=0.2, messages=messages,
        )
        answer = response.choices[0].message.content
        if not answer or not answer.strip():
            raise AIProviderError(f"{provider_name} returned an empty response.")
        return answer.strip()
    except AIProviderError:
        raise
    except Exception as exc:
        raise AIProviderError(f"{provider_name} request failed ({type(exc).__name__}).") from exc


def huggingface_chat(messages: list[dict], api_token: str,
                     model: str = "openai/gpt-oss-120b:cheapest",
                     base_url: str = "https://router.huggingface.co/v1") -> str:
    """Call Hugging Face's managed Inference Providers router (open-weight models)."""
    return _openai_compatible_chat(
        messages, api_token, model, base_url, "Hugging Face Inference Providers"
    )


def openai_chat(messages: list[dict], api_key: str, model: str = "gpt-4o-mini") -> str:
    return _openai_compatible_chat(
        messages, api_key, model, "https://api.openai.com/v1", "OpenAI"
    )


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
