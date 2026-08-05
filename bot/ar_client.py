import json
from pathlib import Path
from typing import Any

import httpx

from bot.parse import FlightQuery


class ARApiError(Exception):
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class ARClient:
    def __init__(
        self,
        base_url: str,
        headers_file: str | Path,
        timeout: float = 30.0,
    ):
        self.base_url = base_url.rstrip("?")
        self.headers_file = Path(headers_file)
        self.timeout = timeout

    def load_headers(self) -> dict[str, str]:
        if not self.headers_file.exists():
            raise ARApiError(
                f"Headers file not found: {self.headers_file}. "
                "Copy headers.example.json to config/headers.json and paste browser headers."
            )
        with self.headers_file.open(encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            raise ARApiError("Headers file must be a JSON object of header name → value.")
        headers = {str(k): str(v) for k, v in data.items() if v is not None}
        # httpx sets Host/Content-Length; strip hop-by-hop if present
        for drop in ("host", "content-length", "connection", "content-encoding"):
            keys = [k for k in headers if k.lower() == drop]
            for k in keys:
                del headers[k]
        return headers

    async def fetch_offers(self, query: FlightQuery) -> dict[str, Any]:
        headers = self.load_headers()
        params = {
            "adt": "1",
            "inf": "0",
            "chd": "0",
            "flexDates": "true",
            "cabinClass": "Economy",
            "flightType": "ONE_WAY",
            "awardBooking": "true",
            "leg": query.leg,
        }
        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
            try:
                response = await client.get(self.base_url, params=params, headers=headers)
            except httpx.TimeoutException as exc:
                raise ARApiError("AR API request timed out.") from exc
            except httpx.HTTPError as exc:
                raise ARApiError(f"AR API request failed: {exc}") from exc

        if response.status_code in (401, 403):
            raise ARApiError(
                "AR API auth failed (401/403). Refresh config/headers.json from the browser.",
                status_code=response.status_code,
            )
        if response.status_code >= 400:
            raise ARApiError(
                f"AR API error HTTP {response.status_code}: {response.text[:200]}",
                status_code=response.status_code,
            )

        try:
            payload = response.json()
        except ValueError as exc:
            raise ARApiError("AR API returned non-JSON response.") from exc
        if not isinstance(payload, dict):
            raise ARApiError("Unexpected AR API response shape.")
        return payload
