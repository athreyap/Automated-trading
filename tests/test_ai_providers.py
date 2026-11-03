import requests
import pytest

from alphafund.ai_providers import AIProviderError, huggingface_chat, ollama_chat


class FakeResponse:
    def raise_for_status(self):
        return None

    def json(self):
        return {"message": {"content": "local answer"}}


def test_ollama_chat_posts_to_local_server(monkeypatch):
    calls = {}

    def fake_post(url, json, timeout):
        calls.update(url=url, json=json, timeout=timeout)
        return FakeResponse()

    monkeypatch.setattr("alphafund.ai_providers.requests.post", fake_post)
    answer = ollama_chat([{"role": "user", "content": "test"}])
    assert answer == "local answer"
    assert calls["url"] == "http://localhost:11434/api/chat"
    assert calls["json"]["model"] == "qwen2.5:7b"


def test_ollama_chat_reports_unreachable_server(monkeypatch):
    def fail_post(*args, **kwargs):
        raise requests.ConnectionError("offline")

    monkeypatch.setattr("alphafund.ai_providers.requests.post", fail_post)
    with pytest.raises(AIProviderError, match="Cannot reach Ollama"):
        ollama_chat([{"role": "user", "content": "test"}])


def test_huggingface_chat_uses_router_and_open_weight_model(monkeypatch):
    calls = {}

    class Choice:
        class Message:
            content = "managed answer"
        message = Message()

    class Completion:
        choices = [Choice()]

    class Chat:
        class Completions:
            def create(self, **kwargs):
                calls.update(kwargs)
                return Completion()
        completions = Completions()

    class Client:
        def __init__(self, **kwargs):
            calls["client"] = kwargs
            self.chat = Chat()

    monkeypatch.setattr("openai.OpenAI", Client)
    answer = huggingface_chat(
        [{"role": "user", "content": "test"}], api_token="test-token"
    )
    assert answer == "managed answer"
    assert calls["client"]["base_url"] == "https://router.huggingface.co/v1"
    assert calls["client"]["api_key"] == "test-token"
    assert calls["model"] == "openai/gpt-oss-120b:cheapest"
