import json
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

from .config import Settings


class UpstreamError(RuntimeError):
    pass


@dataclass
class CacheEntry:
    body: Dict[str, Any]
    expires_at: float
    fetched_at: float


class UpstreamClient:
    """One-process token and response cache. No token is exposed to API callers."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._token = None  # type: Optional[str]
        self._token_expires_at = 0.0
        self._cache = {}  # type: Dict[str, CacheEntry]
        self._lock = threading.Lock()

    def fetch_pool(self, pool_id: int, params: Dict[str, str], refresh: bool) -> Tuple[Dict[str, Any], bool, float]:
        query = urllib.parse.urlencode(sorted(params.items()))
        cache_key = f"{pool_id}?{query}"
        now = time.time()
        with self._lock:
            cached = self._cache.get(cache_key)
            if cached and not refresh and cached.expires_at > now:
                return cached.body, True, cached.fetched_at

            body = self._request_pool(pool_id, params)
            self._cache[cache_key] = CacheEntry(
                body=body,
                fetched_at=now,
                expires_at=now + self.settings.cache_ttl_seconds,
            )
            return body, False, now

    def _request_pool(self, pool_id: int, params: Dict[str, str]) -> Dict[str, Any]:
        token = self._get_token()
        try:
            return self._request_json(f"/market/pool/{pool_id}", token=token, params=params)
        except UpstreamError as exc:
            if "HTTP 401" not in str(exc) and "HTTP 403" not in str(exc):
                raise
            self._token = None
            self._token_expires_at = 0.0
            return self._request_json(f"/market/pool/{pool_id}", token=self._get_token(), params=params)

    def _get_token(self) -> str:
        if self._token and self._token_expires_at > time.time():
            return self._token
        payload = self._request_json("/auth/token", method="POST", body={"username": self.settings.username})
        token = payload.get("token")
        if not isinstance(token, str) or not token:
            raise UpstreamError("上游未返回 token")
        self._token = token
        self._token_expires_at = time.time() + 23 * 60 * 60
        return token

    def _request_json(
        self,
        path: str,
        method: str = "GET",
        body: Optional[Dict[str, Any]] = None,
        token: Optional[str] = None,
        params: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        url = self.settings.api_base + path
        if params:
            url += "?" + urllib.parse.urlencode(params)
        headers = {"Accept": "application/json", "User-Agent": "local-data-platform/0.1"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        data = json.dumps(body).encode("utf-8") if body is not None else None
        if data:
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=self.settings.timeout_seconds) as response:
                raw = response.read()
        except urllib.error.HTTPError as exc:
            raise UpstreamError(f"HTTP {exc.code}") from exc
        except urllib.error.URLError as exc:
            raise UpstreamError(f"网络错误: {exc.reason}") from exc
        try:
            decoded = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise UpstreamError("上游响应不是 JSON") from exc
        if not isinstance(decoded, dict):
            raise UpstreamError("上游响应不是对象")
        return decoded
