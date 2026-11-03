from alphafund.ai_providers import ollama_chat, AIProviderError


class FakeResponse:
    def raise_for_status(self):
        return None

    def json(self):
        return {"message": {"content": "Portfolio review complete"}}


def test_ollama_chat_posts_to_local_server(monkeypatch):
    seen = {}

    def fake_post(url, json, timeout):
        seen["url"] = url
        seen["json"] = json
        seen["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr("alphafund.ai_providers.requests.post", fake_post)
    answer = ollama_chat(
        [{"role": "user", "content": "Review this portfolio"}],
        model="qwen2.5:7b",
        base_url="http://localhost:11434/",
    )
    assert answer == "Portfolio review complete"
    assert seen["url"] == "http://localhost:11434/api/chat"
    assert seen["json"]["model"] == "qwen2.5:7b"
    assert seen["json"]["stream"] is False


def test_ollama_chat_reports_unreachable_server(monkeypatch):
    import requests

    def fail_post(*args, **kwargs):
        raise requests.ConnectionError("offline")

    monkeypatch.setattr("alphafund.ai_providers.requests.post", fail_post)
    try:
        ollama_chat([{"role": "user", "content": "test"}])
        assert False, "Expected AIProviderError"
    except AIProviderError as exc:
        assert "Cannot reach Ollama" in str(exc)
