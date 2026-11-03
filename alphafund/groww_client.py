"""Read-only client for Groww official portfolio endpoints."""
from typing import Any
import requests

class GrowwAPIError(RuntimeError):
    pass

class GrowwReadOnlyClient:
    BASE_URL = "https://api.groww.in/v1"
    def __init__(self, access_token: str, timeout: int = 15):
        if not access_token or not access_token.strip():
            raise GrowwAPIError("Groww access token is missing.")
        self.headers = {"Accept": "application/json", "Authorization": f"Bearer {access_token.strip()}", "X-API-VERSION": "1.0"}
        self.timeout = timeout
        self.session = requests.Session()

    def _get(self, path: str, params: dict | None = None) -> dict[str, Any]:
        try:
            response = self.session.get(f"{self.BASE_URL}/{path}", headers=self.headers, params=params, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
        except requests.Timeout as exc:
            raise GrowwAPIError("Groww API timed out. Try again shortly.") from exc
        except requests.HTTPError as exc:
            code = exc.response.status_code if exc.response is not None else "unknown"
            if code in (401, 403):
                raise GrowwAPIError("Groww rejected the token. Generate a fresh token and update GROWW_ACCESS_TOKEN.") from exc
            raise GrowwAPIError(f"Groww API returned HTTP {code}. Check API access and try again.") from exc
        except (requests.RequestException, ValueError) as exc:
            raise GrowwAPIError("Could not read a valid response from Groww.") from exc
        if not isinstance(data, dict) or data.get("status") != "SUCCESS" or not isinstance(data.get("payload"), dict):
            raise GrowwAPIError("Groww returned an unsuccessful or unexpected response. Check token permissions and API subscription.")
        return data["payload"]

    def get_holdings(self) -> list[dict[str, Any]]:
        rows = self._get("holdings/user").get("holdings", [])
        if not isinstance(rows, list): raise GrowwAPIError("Unexpected holdings response format.")
        return rows

    def get_positions(self, segment: str = "CASH") -> list[dict[str, Any]]:
        if segment not in {"CASH", "FNO"}: raise ValueError("Unsupported Groww segment.")
        rows = self._get("positions/user", {"segment": segment}).get("positions", [])
        if not isinstance(rows, list): raise GrowwAPIError("Unexpected positions response format.")
        return rows

    def get_portfolio(self):
        # Only GET endpoints; intentionally no order-related methods.
        return self.get_holdings(), self.get_positions("CASH")
