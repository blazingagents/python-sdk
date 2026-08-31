from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from typing import Self

import httpx

from ._errors import StreamError


class _ResponseMetadata:
    status_code: int
    headers: httpx.Headers
    request_id: str | None
    content_type: str | None
    content_length: int | None
    content_disposition: str | None

    def _set_response_metadata(self, response: httpx.Response) -> None:
        self.status_code = response.status_code
        self.headers = httpx.Headers(response.headers)
        self.request_id = response.headers.get("x-request-id")
        self.content_type = response.headers.get("content-type")
        content_length = response.headers.get("content-length")
        self.content_length = (
            int(content_length) if content_length is not None else None
        )
        self.content_disposition = response.headers.get("content-disposition")


class _ByteStreamBase(_ResponseMetadata):
    def __init__(self, response: httpx.Response) -> None:
        self._response = response
        self._claimed = False
        self._set_response_metadata(response)

    @property
    def closed(self) -> bool:
        return self._response.is_closed

    def _claim(self) -> None:
        if self._claimed or self.closed:
            msg = "Stream body has already been consumed or closed."
            raise StreamError(
                msg,
                response=self._response,
            )
        self._claimed = True


class ByteStream(_ByteStreamBase):
    """A single-consumer streaming response body."""

    def __iter__(self) -> Iterator[bytes]:
        self._claim()
        return self._consume()

    def _consume(self) -> Iterator[bytes]:
        try:
            yield from self._response.iter_bytes()
        except httpx.HTTPError as error:
            raise StreamError(
                "Stream read failed.",
                response=self._response,
            ) from error
        finally:
            self.close()

    def close(self) -> None:
        self._response.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


class AsyncByteStream(_ByteStreamBase):
    """An asynchronous single-consumer streaming response body."""

    def __aiter__(self) -> AsyncIterator[bytes]:
        self._claim()
        return self._consume()

    async def _consume(self) -> AsyncIterator[bytes]:
        try:
            async for chunk in self._response.aiter_bytes():
                yield chunk
        except httpx.HTTPError as error:
            raise StreamError(
                "Stream read failed.",
                response=self._response,
            ) from error
        finally:
            await self.aclose()

    async def aclose(self) -> None:
        await self._response.aclose()

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.aclose()
