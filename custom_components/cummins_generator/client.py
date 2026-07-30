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

from homeassistant.helpers.aiohttp_client import async_get_clientsession

_LOGGER = logging.getLogger(__name__)

REQUEST_TIMEOUT_SECONDS = 10


class InvalidAuth(Exception):
    """Generator rejected the supplied password."""


class CannotConnect(Exception):
    """Could not reach the generator."""


async def validate_credentials(hass, host: str, password: str) -> None:
    """Probe the generator with the given credentials.

    Raises InvalidAuth on 401 or CannotConnect on any other failure.
    """
    session = async_get_clientsession(hass)
    auth_header = "Basic " + base64.b64encode(
        f"admin:{password}".encode()
    ).decode("ascii")
    url = f"http://{host}/index_data.html"
    timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT_SECONDS)
    try:
        async with session.get(
            url, headers={"Authorization": auth_header}, timeout=timeout
        ) as response:
            if response.status == 401:
                raise InvalidAuth
            if response.status != 200:
                raise CannotConnect(f"HTTP {response.status}")
    except (aiohttp.ClientError, asyncio.TimeoutError) as err:
        raise CannotConnect(str(err)) from err


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

    def update_password(self, password):
        """Change the admin password live."""
        self._auth_header = "Basic " + base64.b64encode(
            f"admin:{password}".encode()
        ).decode("ascii")

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
