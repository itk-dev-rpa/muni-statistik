"""Client for the boost.ai Statistics API v2.

Handles OAuth2 client_credentials (token cache + renewal before expiry) and
thin POST wrappers per endpoint type. All statistics calls take a search filter
with required from_date/to_date.
"""

from __future__ import annotations

import time
from typing import Any

import requests

from robot_framework.credentials import Credentials
from robot_framework.settings import DateRange, Settings

REQUEST_TIMEOUT = 60
# Renew the token this many seconds before it actually expires.
TOKEN_REFRESH_MARGIN = 60


class BoostAuthError(Exception):
    """Error while obtaining an OAuth2 token (e.g. wrong/missing scope)."""


class BoostApiError(Exception):
    """Error from a statistics endpoint (carries HTTP status and response body)."""

    def __init__(self, status_code: int, body: str):
        super().__init__(f"boost API error {status_code}: {body}")
        self.status_code = status_code
        self.body = body


class BoostClient:
    """Authenticated client against Statistics API v2 for a single tenant."""

    def __init__(self, settings: Settings, credentials: Credentials):
        self._settings = settings
        self._credentials = credentials
        self._session = requests.Session()
        self._token: str | None = None
        self._token_expiry: float = 0.0

    def _ensure_token(self) -> str:
        """Fetch a token if we don't have a valid cached one."""
        if self._token and time.time() < self._token_expiry:
            return self._token

        resp = requests.post(
            self._settings.token_url,
            data={
                "grant_type": "client_credentials",
                "client_id": self._credentials.boost_client_id,
                "client_secret": self._credentials.boost_client_secret,
                "scope": self._settings.scope,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=REQUEST_TIMEOUT,
        )
        if not resp.ok:
            raise BoostAuthError(
                f"Token request failed ({resp.status_code}): {resp.text}. "
                f"Check client_id/secret and that scope '{self._settings.scope}' "
                "is granted to the client.")

        payload = resp.json()
        self._token = payload["access_token"]
        expires_in = int(payload.get("expires_in", 3600))
        self._token_expiry = time.time() + expires_in - TOKEN_REFRESH_MARGIN
        return self._token

    def post(self, path: str, body: dict, params: dict | None = None) -> Any:
        """Send an authenticated POST request to a statistics endpoint."""
        token = self._ensure_token()
        resp = self._session.post(
            f"{self._settings.base_url}{path}",
            json=body,
            params=params,
            headers={"Authorization": f"Bearer {token}",
                     "Content-Type": "application/json"},
            timeout=REQUEST_TIMEOUT,
        )
        if not resp.ok:
            raise BoostApiError(resp.status_code, resp.text)
        return resp.json()

    # --- Endpoint wrappers -------------------------------------------------

    def distribution(self, stat: str, date_range: DateRange) -> Any:
        """POST /distribution/{stat}."""
        return self.post(f"/distribution/{stat}", _filter(date_range))

    def frequency(self, stat: str, date_range: DateRange,
                  limit: int | None = None, **filters: Any) -> Any:
        """POST /frequency/{stat}."""
        params = {"limit": limit} if limit is not None else None
        return self.post(f"/frequency/{stat}",
                         _filter(date_range, **filters), params)

    def histogram(self, stat: str, date_range: DateRange,
                  group_by: str = "day") -> Any:
        """POST /histogram/{stat} grouped by time period."""
        return self.post(f"/histogram/{stat}",
                         _filter(date_range, group_by=group_by))

    def token_usage(self, date_range: DateRange) -> Any:
        """POST /aggregates/token_usage."""
        return self.post("/aggregates/token_usage", _filter(date_range))


def _filter(date_range: DateRange, **extra: Any) -> dict:
    """Build the search filter body with required from_date/to_date + extras."""
    body = {"from_date": date_range.iso_from, "to_date": date_range.iso_to}
    body.update(extra)
    return body
