import logging
import asyncio
import aiohttp
import random
import ssl
import time
import platform
import json
from typing import Optional, Dict, Any, List, Tuple
from utils.proxy_manager import ProxyManager

class BaseAPIClient:
    def __init__(
        self,
        base_url: str,
        proxy_manager: ProxyManager,
        rate_limit: int = 1,
        timeout: int = 30
    ):
        self.base_url = base_url.rstrip('/')
        self.proxy_manager = proxy_manager
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self.rate_limiter = asyncio.Semaphore(rate_limit)
        self.session = None
        self.logger = logging.getLogger(self.__class__.__name__)
        self.last_request_time = 0
        self.request_delay = 1.0
        self.success_count = 0
        self.fail_count = 0
        self.proxy_success_map = {}
        self.proxy_blacklist = set()
        self.proxy_scores = {}
        self.last_session_reset = time.time()
        self.session_lifetime = 1800
        self.request_times = []
        self.adaptive_delay = 1.0
        
        self.desktop_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15'
        ]
        self.session_fingerprint = self._generate_session_fingerprint()
        self.successful_proxies = []
        self.tls_versions = ['TLSv1.2', 'TLSv1.3']
        self.cipher_suites = [
            'TLS_AES_128_GCM_SHA256',
            'TLS_AES_256_GCM_SHA384',
            'TLS_CHACHA20_POLY1305_SHA256'
        ]

    def _generate_session_fingerprint(self) -> Dict[str, Any]:
        screen_resolutions = ['1920x1080', '2560x1440', '1440x900', '1366x768', '1600x900']
        gpu_renderers = [
            'ANGLE (NVIDIA GeForce RTX 3060)',
            'ANGLE (NVIDIA GeForce RTX 3070)',
            'ANGLE (AMD Radeon RX 6800)',
            'ANGLE (Intel(R) UHD Graphics 630)'
        ]
        viewport_sizes = [
            {'width': 1536, 'height': 864},
            {'width': 1920, 'height': 1080},
            {'width': 1440, 'height': 900}
        ]
        return {
            'webgl_vendor': 'Google Inc. (NVIDIA)',
            'webgl_renderer': random.choice(gpu_renderers),
            'canvas_hash': f"{random.randint(1000000, 9999999)}",
            'screen_resolution': random.choice(screen_resolutions),
            'viewport': random.choice(viewport_sizes),
            'color_depth': 24,
            'timezone': 'Europe/Berlin',
            'platform': platform.system(),
            'language': 'de-DE',
            'session_id': f"{time.time()}_{random.randint(1000, 9999)}",
            'device_memory': random.choice([4, 8, 16, 32]),
            'hardware_concurrency': random.choice([4, 6, 8, 12, 16]),
            'touch_support': False,
            'webgl_extensions': ['ANGLE_instanced_arrays', 'EXT_blend_minmax'],
            'audio_context': {'sample_rate': 48000, 'state': 'running'},
            'browser_plugins': self._generate_browser_plugins()
        }

    def _generate_browser_plugins(self) -> List[Dict]:
        return [
            {'name': 'Chrome PDF Plugin', 'filename': 'internal-pdf-viewer'},
            {'name': 'Chrome PDF Viewer', 'filename': 'mhjfbmdgcfjbbpaeojofohoefgiehjai'},
            {'name': 'Native Client', 'filename': 'internal-nacl-plugin'}
        ]

    def _get_random_headers(self) -> Dict[str, str]:
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
            'DNT': '1',
            'X-Client-Data': self.session_fingerprint['session_id'],
            'X-Requested-With': 'XMLHttpRequest',
            'X-Device-Memory': str(self.session_fingerprint['device_memory']),
            'X-Hardware-Concurrency': str(self.session_fingerprint['hardware_concurrency'])
        }
        
        header_items = list(headers.items())
        random.shuffle(header_items)
        return dict(header_items)

    def _format_proxy(self, proxy_str: str) -> Optional[str]:
        try:
            if not proxy_str:
                return None
                
            if proxy_str in self.proxy_blacklist:
                return None

            if self.successful_proxies and random.random() < 0.8:
                successful_proxies_sorted = sorted(
                    self.successful_proxies,
                    key=lambda x: self.proxy_scores.get(x, 0),
                    reverse=True
                )
                return random.choice(successful_proxies_sorted[:3])

            if '@' in proxy_str:
                return f"http://{proxy_str}"

            parts = proxy_str.split(':')
            if len(parts) >= 4:
                host = parts[0]
                port = parts[1]
                user = ':'.join(parts[2:-1])
                password = parts[-1].split('@')[0] if '@' in parts[-1] else parts[-1]
                return f"http://{user}:{password}@{host}:{port}"

            return None
        except Exception as e:
            self.logger.error(f"Proxy-Formatierungsfehler: {e}")
            return None

    async def _init_session(self):
        current_time = time.time()
        if (self.session is None or 
            self.session.closed or 
            current_time - self.last_session_reset > self.session_lifetime):
            
            if self.session and not self.session.closed:
                await self.session.close()
            
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            ssl_context.set_ciphers('DEFAULT')
            
            connector = aiohttp.TCPConnector(
                ssl=ssl_context,
                force_close=False,
                limit=100,
                ttl_dns_cache=300,
                enable_cleanup_closed=True,
                keepalive_timeout=30
            )
            
            self.session = aiohttp.ClientSession(
                timeout=self.timeout,
                headers=self._get_random_headers(),
                connector=connector,
                cookie_jar=aiohttp.CookieJar(unsafe=True),
                trust_env=True
            )
            self.session._fingerprint = self.session_fingerprint
            self.last_session_reset = current_time

    def _update_adaptive_delay(self, response_time: float, success: bool):
        self.request_times.append(response_time)
        if len(self.request_times) > 10:
            self.request_times.pop(0)
        
        avg_response_time = sum(self.request_times) / len(self.request_times)
        if success:
            self.adaptive_delay = max(0.5, min(avg_response_time * 0.8, self.adaptive_delay * 0.95))
        else:
            self.adaptive_delay = min(5.0, max(avg_response_time * 1.2, self.adaptive_delay * 1.5))

    async def _make_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict] = None,
        data: Optional[Dict] = None,
        json: Optional[Dict] = None
    ) -> Optional[Dict[str, Any]]:
        await self._init_session()
        endpoint = endpoint.lstrip('/')
        url = f"{self.base_url}/{endpoint}"
        retry_count = 0
        max_retries = len(self.proxy_manager.proxies)
        start_time = time.time()

        current_time = time.time()
        time_diff = current_time - self.last_request_time
        if time_diff < self.adaptive_delay:
            await asyncio.sleep(self.adaptive_delay - time_diff)

        while retry_count < max_retries:
            try:
                proxy = None
                if self.proxy_manager:
                    proxy_data = await self.proxy_manager.get_proxy()
                    if proxy_data:
                        proxy_str = proxy_data if isinstance(proxy_data, str) else proxy_data.get('http', '')
                        proxy = self._format_proxy(proxy_str)
                        if not proxy:
                            retry_count += 1
                            continue

                headers = self._get_random_headers()
                headers['X-Request-ID'] = f"{time.time()}_{random.randint(1000, 9999)}"
                headers['X-Real-IP'] = f"{random.randint(1, 255)}.{random.randint(1, 255)}.{random.randint(1, 255)}.{random.randint(1, 255)}"

                async with self.session.request(
                    method=method,
                    url=url,
                    params=params,
                    data=data,
                    json=json,
                    proxy=proxy,
                    headers=headers,
                    timeout=self.timeout,
                    allow_redirects=True,
                    compress=True
                ) as response:
                    self.last_request_time = time.time()
                    response_time = time.time() - start_time
                    
                    if response.status == 200:
                        self._update_adaptive_delay(response_time, True)
                        if proxy:
                            self._track_proxy_success(proxy)
                        
                        content_type = response.headers.get('Content-Type', '')
                        if 'application/json' in content_type:
                            return await response.json()
                        else:
                            text_response = await response.text()
                            return {"html_content": text_response}
                            
                    elif response.status in [429, 403, 503, 407]:
                        self._update_adaptive_delay(response_time, False)
                        if proxy and self.proxy_manager:
                            await self.proxy_manager.mark_failed(proxy_data)
                        retry_count += 1
                        
                        wait_time = min(300, (2 ** retry_count) + random.uniform(0, 1))
                        await asyncio.sleep(wait_time)
                        continue
                        
                    else:
                        retry_count += 1
                        await asyncio.sleep(self.adaptive_delay)
                        continue

            except Exception as e:
                self.logger.error(f"Fehler bei Anfrage an {url}: {str(e)}")
                if proxy and self.proxy_manager:
                    await self.proxy_manager.mark_failed(proxy_data)
                retry_count += 1
                
                if isinstance(e, aiohttp.ClientTimeout):
                    wait_time = random.uniform(2.0, 5.0)
                elif isinstance(e, aiohttp.ClientConnectionError):
                    wait_time = random.uniform(1.0, 3.0)
                else:
                    wait_time = random.uniform(0.5, 2.0)
                    
                await asyncio.sleep(wait_time)
                continue

        return None

    def _track_proxy_success(self, proxy: str):
        if proxy not in self.proxy_scores:
            self.proxy_scores[proxy] = 1.0
        self.proxy_scores[proxy] *= 1.1
        
        if proxy not in self.successful_proxies:
            self.successful_proxies.append(proxy)
            if len(self.successful_proxies) > 10:
                self.successful_proxies = sorted(
                    self.successful_proxies,
                    key=lambda x: self.proxy_scores.get(x, 0),
                    reverse=True
                )[:10]

    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()
