import re
import time

import httpx

TOKEN_URL = "https://www.aerolineas.com.ar"
TOKEN_RE = re.compile(r'window\.__ACCESS_TOKEN__\s*=\s*"([^"]+)"')
EXP_RE = re.compile(r"window\.__TOKEN_EXPIRATION__\s*=\s*(\d+)")
TOKEN_SKEW_SECONDS = 60

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) "
        "Version/26.6 Safari/605.1.15"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-AR,es;q=0.9",
}


class TokenError(Exception):
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class AccessTokenProvider:
    def __init__(
        self,
        token_url: str = TOKEN_URL,
        timeout: float = 30.0,
    ):
        self.token_url = token_url
        self.timeout = timeout
        self._access_token: str | None = None
        self._token_expiration: int = 0

    def _token_valid(self) -> bool:
        return bool(
            self._access_token
            and time.time() < self._token_expiration - TOKEN_SKEW_SECONDS
        )

    async def _fetch(self) -> str:
        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
            try:
                response = await client.get(self.token_url, headers=BROWSER_HEADERS)
            except httpx.TimeoutException as exc:
                raise TokenError(
                    "Error interno, intentar nuevamente mas tarde",
                ) from exc
            except httpx.HTTPError as exc:
                raise TokenError(
                    "Error interno, intentar nuevamente mas tarde",
                ) from exc

        if response.status_code >= 400:
            raise TokenError(
                "Error interno, intentar nuevamente mas tarde",
                status_code=response.status_code,
            )

        html = response.text
        token_match = TOKEN_RE.search(html)
        if not token_match:
            raise TokenError("Error interno, intentar nuevamente mas tarde")

        token = token_match.group(1)
        exp_match = EXP_RE.search(html)
        expiration = int(exp_match.group(1)) if exp_match else int(time.time()) + 3600

        self._access_token = token
        self._token_expiration = expiration
        return token

    async def get(self, *, force: bool = False) -> str:
        if force or not self._token_valid():
            return await self._fetch()
        assert self._access_token is not None
        return self._access_token
