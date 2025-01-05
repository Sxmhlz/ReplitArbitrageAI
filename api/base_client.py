import logging
import asyncio
import aiohttp
import random
import ssl
import time
import platform
import json
from typing import Optional, Dict, Any, List, Set
from collections import deque
from datetime import datetime
from utils.proxy_manager import ProxyManager

class BaseAPIClient:
    def __init__(
        self,
        base_url: str,
        proxy_manager: ProxyManager,
        rate_limit: int = 1,
        timeout: int = 30,
        client_type: str = 'default'
    ):
        self.base_url = base_url.rstrip('/')
        self.proxy_manager = proxy_manager
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self.rate_limiter = asyncio.Semaphore(rate_limit)
        self.session = None
        self.logger = logging.getLogger(self.__class__.__name__)
        self.client_type = client_type

        # Performance Tracking
        self.last_request_time = 0
        self.request_delay = 1.0
        self.success_count = 0
        self.fail_count = 0
        self.request_times = deque(maxlen=50)
        self.successful_proxies = set()
        self.proxy_performance = {}
        self.proxy_errors = {}

        # Session Management
        self.session_start_time = time.time()
        self.session_requests = 0
        self.max_session_requests = 100
        self.session_lifetime = 1800  # 30 minutes

        # Request Queue
        self.request_queue = asyncio.Queue()
        self.active_requests = 0
        self.max_concurrent_requests = 5

        # Headers
        self.desktop_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15'
        ]
        
        self.ios_agents = [
            'alias/1.33.1 (iPhone; iOS 17.5.1; Scale/3.00) Locale/en'
        ]

    def _get_headers(self) -> Dict[str, str]:
        """Generiert API-spezifische Headers."""
        if self.client_type == 'alias':
            headers = {
                'User-Agent': random.choice(self.ios_agents),
                'Authorization': 'Bearer dpH4GMpJmzgKrMgh1wntLf8Cq3qQsW3o1HiMlzyzVss.6cBDEA1gMmvUgnnikhTycNocfCsd6DcCGtcJYP9zeiY',
                'X-Algolia-API-Key': '838ecd564b6aedc176ff73b67087ff43',
                'X-Algolia-Application-Id': '2FWOTDVM2O',
                'Accept': 'application/json',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br'
            }
        else:
            chrome_version = f"{random.randint(115, 120)}.0.{random.randint(0, 9999)}.{random.randint(0, 999)}"
            headers = {
                'User-Agent': random.choice(self.desktop_agents),
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Cache-Control': 'max-age=0',
                'Sec-Ch-Ua': f'"Google Chrome";v="{chrome_version}", "Chromium";v="{chrome_version}"',
                'Sec-Ch-Ua-Mobile': '?0',
                'Sec-Ch-Ua-Platform': f'"{platform.system()}"',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Sec-Fetch-User': '?1',
                'DNT': '1'
            }

        header_items = list(headers.items())
        random.shuffle(header_items)
        return dict(header_items)

    async def _make_request(self, method: str, endpoint: str, **kwargs) -> Optional[Dict[str, Any]]:
        """Führt eine HTTP-Anfrage aus und verarbeitet die Antwort."""
        if not endpoint.startswith(('http://', 'https://')):
            url = f"{self.base_url}/{endpoint.lstrip('/')}"
        else:
            url = endpoint

        try:
            if not self.session or self.session.closed:
                self.session = aiohttp.ClientSession(timeout=self.timeout)

            headers = self._get_headers()
            if 'headers' in kwargs:
                headers.update(kwargs.pop('headers'))

            proxy = await self.proxy_manager.get_proxy()
            if proxy:
                kwargs['proxy'] = proxy.get('http')

            async with self.rate_limiter:
                async with self.session.request(method, url, headers=headers, **kwargs) as response:
                    content_type = response.headers.get('Content-Type', '').lower()
                    
                    if 'text/html' in content_type:
                        return {
                            'type': 'html',
                            'content': await response.text(),
                            'status': response.status,
                            'url': str(response.url)
                        }
                    elif 'application/json' in content_type:
                        try:
                            json_data = await response.json()
                            return {
                                'type': 'json',
                                'content': json_data,
                                'status': response.status,
                                'url': str(response.url)
                            }
                        except json.JSONDecodeError:
                            text_content = await response.text()
                            return {
                                'type': 'text',
                                'content': text_content,
                                'status': response.status,
                                'url': str(response.url)
                            }
                    else:
                        text_content = await response.text()
                        try:
                            json_data = json.loads(text_content)
                            return {
                                'type': 'json',
                                'content': json_data,
                                'status': response.status,
                                'url': str(response.url)
                            }
                        except json.JSONDecodeError:
                            return {
                                'type': 'text',
                                'content': text_content,
                                'status': response.status,
                                'url': str(response.url)
                            }

        except Exception as e:
            self.logger.error(f"Request Fehler ({method} {url}): {str(e)}")
            return None

    async def get(self, endpoint: str, **kwargs) -> Optional[Dict[str, Any]]:
        """Führt eine GET-Anfrage aus."""
        return await self._make_request('GET', endpoint, **kwargs)

    async def post(self, endpoint: str, **kwargs) -> Optional[Dict[str, Any]]:
        """Führt eine POST-Anfrage aus."""
        return await self._make_request('POST', endpoint, **kwargs)

    async def put(self, endpoint: str, **kwargs) -> Optional[Dict[str, Any]]:
        """Führt eine PUT-Anfrage aus."""
        return await self._make_request('PUT', endpoint, **kwargs)

    async def delete(self, endpoint: str, **kwargs) -> Optional[Dict[str, Any]]:
        """Führt eine DELETE-Anfrage aus."""
        return await self._make_request('DELETE', endpoint, **kwargs)

    async def close(self):
        """Schließt die Session und gibt Ressourcen frei."""
        if self.session and not self.session.closed:
            await self.session.close()
            self.logger.info("BaseAPIClient Session geschlossen")

    def __del__(self):
        """Destruktor zur Sicherstellung der Ressourcenfreigabe."""
        if self.session and not self.session.closed:
            asyncio.run(self.close())

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
