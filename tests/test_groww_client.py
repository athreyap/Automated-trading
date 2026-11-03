import hashlib
from unittest.mock import Mock

import requests
import pytest

from alphafund import groww_client


def test_generate_access_token_uses_documented_checksum(monkeypatch):
    monkeypatch.setattr(groww_client.time, "time", lambda: 1719830400)
    response = Mock()
    response.json.return_value = {"token": "test-access-token", "isActive": True}
    response.raise_for_status.return_value = None
    captured = {}

    def fake_post(url, **kwargs):
        captured["url"] = url
        captured.update(kwargs)
        return response

    monkeypatch.setattr(groww_client.requests, "post", fake_post)
    token = groww_client.generate_access_token("api-key", "api-secret")
    expected = hashlib.sha256(b"api-secret1719830400").hexdigest()
    assert token == "test-access-token"
    assert captured["url"] == "https://api.groww.in/v1/token/api/access"
    assert captured["headers"]["Authorization"] == "Bearer api-key"
    assert captured["json"] == {"key_type": "approval", "checksum": expected, "timestamp": "1719830400"}


def test_generate_access_token_rejects_missing_credentials():
    with pytest.raises(groww_client.GrowwAPIError):
        groww_client.generate_access_token("", "secret")


def test_generate_access_token_handles_http_auth_failure(monkeypatch):
    response = Mock()
    response.status_code = 401
    error = requests.HTTPError(response=response)
    mock_response = Mock()
    mock_response.raise_for_status.side_effect = error
    monkeypatch.setattr(groww_client.requests, "post", lambda *a, **k: mock_response)
    with pytest.raises(groww_client.GrowwAPIError, match="did not authorize"):
        groww_client.generate_access_token("key", "secret")


def test_read_only_client_only_fetches_holdings_and_cash_positions(monkeypatch):
    client = groww_client.GrowwReadOnlyClient("token")
    calls = []

    def fake_get(url, **kwargs):
        calls.append((url, kwargs))
        response = Mock()
        response.raise_for_status.return_value = None
        if url.endswith("/holdings/user"):
            response.json.return_value = {"status": "SUCCESS", "payload": {"holdings": []}}
        else:
            response.json.return_value = {"status": "SUCCESS", "payload": {"positions": []}}
        return response

    monkeypatch.setattr(client.session, "get", fake_get)
    assert client.get_portfolio() == ([], [])
    assert [call[0].rsplit("/", 1)[-1] for call in calls] == ["holdings/user", "positions/user"]
    assert calls[1][1]["params"] == {"segment": "CASH"}
    assert not hasattr(client, "place_order")
