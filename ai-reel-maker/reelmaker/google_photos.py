import mimetypes
import time
import tempfile
from pathlib import Path

import requests
from google_auth_oauthlib.flow import Flow

SCOPE = ["https://www.googleapis.com/auth/photospicker.mediaitems.readonly"]
API = "https://photospicker.googleapis.com/v1"


class GooglePhotosPicker:
    def __init__(self, config):
        self.config = config

    def _client_config(self):
        return {
            "web": {
                "client_id": self.config["client_id"],
                "client_secret": self.config["client_secret"],
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [self.config["redirect_uri"]],
            }
        }

    def authorization_url(self):
        flow = Flow.from_client_config(
            self._client_config(),
            scopes=SCOPE,
            redirect_uri=self.config["redirect_uri"],
        )
        url, state = flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
            prompt="consent",
        )
        return url, state

    def exchange_code(self, code, expected_state):
        flow = Flow.from_client_config(
            self._client_config(),
            scopes=SCOPE,
            state=expected_state,
            redirect_uri=self.config["redirect_uri"],
        )
        flow.fetch_token(code=code)
        credentials = flow.credentials
        return {
            "token": credentials.token,
            "refresh_token": credentials.refresh_token,
            "token_uri": credentials.token_uri,
            "client_id": credentials.client_id,
            "client_secret": credentials.client_secret,
            "scopes": list(credentials.scopes or SCOPE),
        }

    def _headers(self, credentials):
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request

        token = Credentials(
            token=credentials.get("token"),
            refresh_token=credentials.get("refresh_token"),
            token_uri=credentials.get("token_uri"),
            client_id=credentials.get("client_id"),
            client_secret=credentials.get("client_secret"),
            scopes=credentials.get("scopes", SCOPE),
        )
        if token.expired and token.refresh_token:
            token.refresh(Request())
            credentials["token"] = token.token
        return {"Authorization": f"Bearer {token.token}"}

    def create_session(self, credentials):
        response = requests.post(
            f"{API}/sessions",
            headers=self._headers(credentials),
            json={},
            timeout=30,
        )
        response.raise_for_status()
        return response.json()

    @staticmethod
    def _seconds(value):
        if isinstance(value, (int, float)):
            return float(value)
        value = str(value).strip().lower()
        if value.endswith("s"):
            value = value[:-1]
        return max(1.0, float(value))

    def get_selected_items(self, credentials, session_id):
        headers = self._headers(credentials)
        deadline = time.time() + 120

        while time.time() < deadline:
            response = requests.get(
                f"{API}/sessions/{session_id}",
                headers=headers,
                timeout=30,
            )
            response.raise_for_status()
            session = response.json()
            if session.get("mediaItemsSet"):
                break
            interval = session.get("pollingConfig", {}).get("pollInterval", "5s")
            time.sleep(min(self._seconds(interval), 10))
        else:
            raise TimeoutError("Google Photos selection was not completed within 120 seconds.")

        items = []
        page_token = None
        while True:
            params = {"sessionId": session_id}
            if page_token:
                params["pageToken"] = page_token
            response = requests.get(
                f"{API}/mediaItems",
                headers=headers,
                params=params,
                timeout=30,
            )
            response.raise_for_status()
            payload = response.json()
            items.extend(payload.get("mediaItems", []))
            page_token = payload.get("nextPageToken")
            if not page_token:
                break
        return items

    def download_items(self, credentials, items):
        headers = self._headers(credentials)
        destination = Path(tempfile.gettempdir()) / "ai_reel_maker_google"
        destination.mkdir(parents=True, exist_ok=True)
        paths = []

        for index, item in enumerate(items):
            media_file = item.get("mediaFile", {})
            base_url = media_file.get("baseUrl")
            mime_type = media_file.get("mimeType", "application/octet-stream")
            if not base_url:
                continue

            is_video = mime_type.startswith("video/")
            download_url = base_url + ("=dv" if is_video else "=d")
            response = requests.get(download_url, headers=headers, timeout=180)
            response.raise_for_status()

            extension = mimetypes.guess_extension(mime_type) or (".mp4" if is_video else ".jpg")
            filename = f"google_photos_{index:03d}{extension}"
            target = destination / filename
            target.write_bytes(response.content)
            paths.append(str(target))

        return paths
