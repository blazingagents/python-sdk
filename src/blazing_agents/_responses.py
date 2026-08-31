from __future__ import annotations

import httpx


class Completion(str):
    """Buffered completion text with the originating response correlation."""

    request_id: str | None
    _response: httpx.Response

    def __new__(cls, content: str, response: httpx.Response) -> Completion:
        value = super().__new__(cls, content)
        value.request_id = response.headers.get("x-request-id")
        value._response = response
        return value
