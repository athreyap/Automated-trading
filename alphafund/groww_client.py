"""Read-only Groww client and API-key authentication helper.

This module deliberately exposes no order placement methods.
"""
from __future__ import annotations

import hashlib
import time
from typing import Any

import requests


class GrowwAPIError(RuntimeError):
    pass


def generate_access_token(api_key: str, api_secret: str, timeout: int = 15) -> str:
    """Exchange API key + secret for a daily token after daily Groww approval."""
    api_key = (api_key or "").strip()
    api_secret = (api_secret or "").strip()
    if not api_key or not api_secret:
        raise GrowwAPIError("Groww API key or API secret is missing.")
    timestamp = str(int(time.time()))
    checksum = hashlib.sha256((api_secret + timestamp).encode("utf-8")).hexdigest()
    try:
        response = requests.post(
            "https://api.groww.in/v1/token/api/access",
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
            json={"key_type": "approval", "checksum": checksum, "timestamp": timestamp},
            timeout=timeout,
        )
        response.raise_for_status()
        data = response.json()
    except requests.Timeout as exc:
        raise GrowwAPIError("Groww authentication timed out. Try again.") from exc
    except requests.HTTPError as exc:
        code = exc.response.status_code if exc.response is not None else "unknown"
        if code in (401, 403):
            raise GrowwAPIError(
                "Groww did not authorize token generation. Check the API key and secret, "
                "and approve the key for today on Groww Cloud → API Keys."
            ) from exc
        raise GrowwAPIError(f"Groww token endpoint returned HTTP {code}.") from exc
    except (requests.RequestException, ValueError) as exc:
        raise GrowwAPIError("Could not read a valid response from Groww authentication.") from exc

    if not isinstance(data, dict):
        raise GrowwAPIError("Groww returned an unexpected authentication response.")
    payload = data.get("payload") if isinstance(data.get("payload"), dict) else data
    token = payload.get("token") if isinstance(payload, dict) else None
    if data.get("status") == "FAILURE" or not isinstance(token, str) or not token.strip():
        error = data.get("error") if isinstance(data.get("error"), dict) else {}
        raise GrowwAPIError(str(error.get("message") or "Groww did not return an access token."))
    return token.strip()


class GrowwReadOnlyClient:
    BASE_URL = "https://api.groww.in/v1"

    def __init__(self, access_token: str, timeout: int = 15):
        if not access_token or not access_token.strip():
            raise GrowwAPIError("Groww access token is missing.")
        self.headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {access_token.strip()}",
            "X-API-VERSION": "1.0",
        }
        self.timeout = timeout
        self.session = requests.Session()

    def _get(self, path: str, params: dict | None = None) -> dict[str, Any]:
        try:
            response = self.session.get(
                f"{self.BASE_URL}/{path}", headers=self.headers,
                params=params, timeout=self.timeout
            )
            response.raise_for_status()
            data = response.json()
        except requests.Timeout as exc:
            raise GrowwAPIError("Groww API timed out. Try again shortly.") from exc
        except requests.HTTPError as exc:
            code = exc.response.status_code if exc.response is not None else "unknown"
            if code in (401, 403):
                raise GrowwAPIError(
                    "Groww rejected the access token. Approve the API key for today "
                    "and refresh the portfolio."
                ) from exc
            raise GrowwAPIError(f"Groww API returned HTTP {code}. Check API access and try again.") from exc
        except (requests.RequestException, ValueError) as exc:
            raise GrowwAPIError("Could not read a valid response from Groww.") from exc
        if not isinstance(data, dict) or data.get("status") != "SUCCESS" or not isinstance(data.get("payload"), dict):
            raise GrowwAPIError("Groww returned an unsuccessful or unexpected response. Check API permissions.")
        return data["payload"]

    def get_holdings(self) -> list[dict[str, Any]]:
        rows = self._get("holdings/user").get("holdings", [])
        if not isinstance(rows, list):
            raise GrowwAPIError("Unexpected holdings response format.")
        return rows

    def get_positions(self, segment: str = "CASH") -> list[dict[str, Any]]:
        if segment not in {"CASH", "FNO"}:
            raise ValueError("Unsupported Groww segment.")
        rows = self._get("positions/user", {"segment": segment}).get("positions", [])
        if not isinstance(rows, list):
            raise GrowwAPIError("Unexpected positions response format.")
        return rows

    def get_portfolio(self):
        # Only GET endpoints; intentionally no order-related methods.
        return self.get_holdings(), self.get_positions("CASH")
