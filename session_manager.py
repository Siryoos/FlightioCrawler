from __future__ import annotations

import aiohttp
from typing import Optional

from requests.selenium_handler import SeleniumHandler


class SessionManager:
    """Unified session manager for HTTP and browser sessions."""

    def __init__(self) -> None:
        self._http_session: Optional[aiohttp.ClientSession] = None
        self._selenium: Optional[SeleniumHandler] = None

    async def get_http_session(self) -> aiohttp.ClientSession:
        if not self._http_session:
            self._http_session = aiohttp.ClientSession()
        return self._http_session

    def get_selenium(self) -> SeleniumHandler:
        if not self._selenium:
            self._selenium = SeleniumHandler()
            self._selenium.setup_driver()
        return self._selenium

    async def close(self) -> None:
        if self._http_session and not self._http_session.closed:
            await self._http_session.close()
        if self._selenium:
            self._selenium.close_driver()
            self._selenium = None
