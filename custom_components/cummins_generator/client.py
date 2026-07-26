"""Rate-limited HTTP client for the Cummins generator.

The generator's embedded controller has a flakey network stack and locks
up under concurrent requests. Every request from every platform must go
through a single shared instance of this client so we can serialize
them and enforce a minimum gap between requests.
"""
import asyncio
import base64
import logging
import aiohttp

_LOGGER = logging.getLogger(__name__)

REQUEST_TIMEOUT_SECONDS = 10


class GeneratorClient:
    """Serialized, rate-limited HTTP client for one generator."""

    def __init__(self, hass, host, password, min_gap_ms):
        self._hass = hass
        self.host = host
        self._auth_header = "Basic " + base64.b64encode(
            f"admin:{password}".encode()
        ).decode("ascii")
        self._min_gap = max(0, min_gap_ms) / 1000.0
        self._lock = asyncio.Lock()
        self._session: aiohttp.ClientSession | None = None
        self._last_request_end = 0.0

    def update_min_gap(self, min_gap_ms):
        """Change the minimum inter-request gap live."""
        self._min_gap = max(0, min_gap_ms) / 1000.0

    async def get(self, path: str) -> str:
        """Issue a serialized, rate-limited GET and return the body text."""
        headers = {"Authorization": self._auth_header}
        timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT_SECONDS)
        url = f"http://{self.host}{path}"

        async with self._lock:
            if self._session is None:
                self._session = aiohttp.ClientSession()

            now = self._hass.loop.time()
            wait = self._min_gap - (now - self._last_request_end)
            if wait > 0:
                _LOGGER.debug("Sleeping %.3fs before %s", wait, path)
                await asyncio.sleep(wait)

            try:
                async with self._session.get(
                    url, headers=headers, timeout=timeout
                ) as response:
                    if response.status != 200:
                        raise aiohttp.ClientResponseError(
                            response.request_info,
                            response.history,
                            status=response.status,
                            message=f"HTTP {response.status} for {path}",
                            headers=response.headers,
                        )
                    return await response.text()
            finally:
                self._last_request_end = self._hass.loop.time()

    async def close(self):
        """Close the underlying aiohttp session."""
        if self._session is not None:
            await self._session.close()
            self._session = None
