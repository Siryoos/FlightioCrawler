from __future__ import annotations

import aiohttp
from typing import Optional

from requests.selenium_handler import SeleniumHandler


class SessionManager:
    """Unified session manager for HTTP and browser sessions."""

    def __init__(self) -> None:
        """
        Initialize the SessionManager with no active HTTP or Selenium sessions.
        """
        self._http_session: Optional[aiohttp.ClientSession] = None
        self._selenium: Optional[SeleniumHandler] = None

    async def get_http_session(self) -> aiohttp.ClientSession:
        """
        Asynchronously retrieves the HTTP client session, creating a new `aiohttp.ClientSession` if one does not already exist.
        
        Returns:
            aiohttp.ClientSession: The managed asynchronous HTTP client session.
        """
        if not self._http_session:
            self._http_session = aiohttp.ClientSession()
        return self._http_session

    def get_selenium(self) -> SeleniumHandler:
        """
        Return the SeleniumHandler instance, initializing and setting up the browser driver if necessary.
        
        Returns:
            SeleniumHandler: The active Selenium browser handler for automated browser interactions.
        """
        if not self._selenium:
            self._selenium = SeleniumHandler()
            self._selenium.setup_driver()
        return self._selenium

    async def close(self) -> None:
        """
        Asynchronously closes the HTTP session and Selenium browser driver if they are active.
        
        Releases resources by closing the HTTP client session and shutting down the Selenium driver, resetting the Selenium handler reference.
        """
        if self._http_session and not self._http_session.closed:
            await self._http_session.close()
        if self._selenium:
            self._selenium.close_driver()
            self._selenium = None
