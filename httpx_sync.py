from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property, lru_cache
from typing import TYPE_CHECKING, Any, cast

from ikea_api.abc import (
    SyncExecutor,
    EndpointInfo,
    EndpointResponse,
    RequestInfo,
    ResponseInfo,
    SessionInfo,
)

if TYPE_CHECKING:
    import httpx


@dataclass
class HttpxResponseInfo(ResponseInfo):
    response: httpx.Response

    def __post_init__(self) -> None:
        self.headers = cast("httpx.Headers", self.response.headers)  # type: ignore
        self.status_code = cast(int, self.response.status_code)  # type: ignore

    @cached_property
    def text(self) -> str:
        return self.response.text

    @cached_property
    def json(self) -> Any:
        return self.response.json()

    @property
    def is_success(self) -> bool:
        return self.response.is_success


@lru_cache
def get_cached_session(headers: frozenset[tuple[str, str]]) -> httpx.Client:
    try:
        import httpx
    except ImportError:
        raise RuntimeError(
            "To use httpx executor you need httpx to be installed. "
            + "Run 'pip install \"ikea_api[httpx]\"' to do so."
        )

    return httpx.Client(headers=dict(headers))


def get_session_from_info(session_info: SessionInfo) -> httpx.Client:
    return get_cached_session(headers=frozenset(session_info.headers.items()))


class HttpxExecutor(SyncExecutor):
    @staticmethod
    def request(request: RequestInfo) -> HttpxResponseInfo:
        session = get_session_from_info(request.session_info)
        response = session.request(  # type: ignore
            method=request.method,
            url=request.session_info.base_url + request.url,
            params=request.params,
            data=request.data,
            json=request.json,
            headers=request.headers,
        )
        return HttpxResponseInfo(response)


def run(endpoint: EndpointInfo[EndpointResponse]) -> EndpointResponse:
    return HttpxExecutor.run(endpoint)
