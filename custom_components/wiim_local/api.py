"""Small asynchronous client for the documented WiiM HTTPS API."""

import asyncio
import ipaddress
import json
import math
import re
from urllib.parse import urlsplit

import aiohttp


class WiiMError(Exception):
    """A request failed or the device returned an invalid response."""


def validate_host(host: str) -> str:
    """Accept only a host or IP, never a URL, path, port or credentials."""
    host = host.strip()
    try:
        ipaddress.ip_address(host)
    except ValueError:
        if len(host) > 253 or not all(
            re.fullmatch(r"[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?", part)
            for part in host.rstrip(".").split(".")
        ):
            raise ValueError("Enter an IP address or hostname") from None
    return host


def number(value, default=None):
    """Read finite device numbers without breaking entity updates."""
    try:
        result = float(value)
        return result if math.isfinite(result) else default
    except (TypeError, ValueError):
        return default


def identity(info: dict) -> str:
    """Require a device-provided stable identity."""
    value = info.get("uuid") or info.get("MAC")
    if not isinstance(value, str) or not value.strip():
        raise WiiMError("Device did not report a unique identity")
    return value.strip().lower()


class WiiMClient:
    def __init__(
        self, session: aiohttp.ClientSession, host: str, verify_ssl: bool = True
    ):
        self.session = session
        host = validate_host(host)
        self.url = (
            f"https://[{host}]/httpapi.asp"
            if ":" in host
            else f"https://{host}/httpapi.asp"
        )
        self.verify_ssl = verify_ssl
        self.lock = asyncio.Lock()

    async def request(self, command: str, *, object_response: bool = False):
        """Encode the whole command as one query parameter; never retry writes."""
        try:
            async with (
                self.lock,
                self.session.get(
                    self.url,
                    params={"command": command},
                    ssl=self.verify_ssl,
                    timeout=aiohttp.ClientTimeout(total=10),
                    allow_redirects=False,
                ) as response,
            ):
                response.raise_for_status()
                if response.status != 200:
                    raise WiiMError("Unexpected device HTTP status")
                text = (await response.text()).strip()
        except (aiohttp.ClientError, TimeoutError) as err:
            raise WiiMError("Cannot communicate with WiiM") from err
        try:
            result = json.loads(text)
        except ValueError:
            result = text
        if isinstance(result, dict) and str(result.get("status", "")).lower() in {
            "failed",
            "fail",
            "error",
        }:
            raise WiiMError("Device rejected command")
        if object_response:
            if not isinstance(result, dict) or not result:
                raise WiiMError("Invalid device response")
        elif result != "OK" and not (
            isinstance(result, dict) and str(result.get("status", "")).upper() == "OK"
        ):
            raise WiiMError("Device did not acknowledge command")
        return result

    async def info(self):
        info = await self.request("getStatusEx", object_response=True)
        identity(info)
        return info

    async def player(self):
        data = await self.request("getPlayerStatus", object_response=True)
        if data.get("status") not in {"play", "pause", "stop", "loading"}:
            raise WiiMError("Invalid player status")
        return data

    async def play_url(self, url: str):
        parsed = urlsplit(url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("Media must be an HTTP or HTTPS audio URL")
        await self.request(f"setPlayerCmd:play:{url}")
