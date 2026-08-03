from __future__ import annotations

from types import TracebackType
from typing import Self

import httpx


class HttpClientOwner:
    """Own or borrow one persistent synchronous HTTPX client.

    Provider clients call ``_initialize_http_client`` once in their constructor.
    When no client is injected, this object owns one persistent client and closes
    it through ``close`` or the context-manager protocol. Injected clients remain
    owned by their caller and are never closed here.
    """

    _http_client: httpx.Client
    _owns_http_client: bool
    _owned_http_client_closed: bool

    def _initialize_http_client(
        self,
        http_client: httpx.Client | None,
        *,
        timeout: float | httpx.Timeout,
        follow_redirects: bool = True,
    ) -> None:
        if hasattr(self, "_http_client"):
            raise RuntimeError("HTTP client lifecycle was initialized more than once")
        self._owns_http_client = http_client is None
        self._http_client = http_client or httpx.Client(
            timeout=timeout,
            follow_redirects=follow_redirects,
        )
        self._owned_http_client_closed = False

    @property
    def owns_http_client(self) -> bool:
        return self._owns_http_client

    def close(self) -> None:
        """Close only a client created by this object; safe to call repeatedly."""

        if not self._owns_http_client or self._owned_http_client_closed:
            return
        self._http_client.close()
        self._owned_http_client_closed = True

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        del exc_type, exc_value, traceback
        self.close()


__all__ = ["HttpClientOwner"]
