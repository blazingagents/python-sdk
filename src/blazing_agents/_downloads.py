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
        """Copy response headers and status onto the stream."""
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
        """Initialize ByteStreamBase.

        Args:
            response: HTTPX response supplying the body and response metadata.
        """
        self._response = response
        self._claimed = False
        self._set_response_metadata(response)

    @property
    def closed(self) -> bool:
        """Return whether the HTTPX response is closed.

        Returns:
            True if the response is closed.
        """
        return self._response.is_closed

    def _claim(self) -> None:
        """Claim the response body for its single consumer."""
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
        """Claim the body and return its single-consumer iterator.

        Returns:
            Single-consumer iterator over response chunks.

        Raises:
            StreamError: The stream is consumed, closed, or fails to complete.
        """
        self._claim()
        return self._consume()

    def _consume(self) -> Iterator[bytes]:
        """Yield response chunks and close the response when consumption ends.

        Raises:
            StreamError: Stream read failed.
        """
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
        """Close the response and release resources."""
        self._response.close()

    def __enter__(self) -> Self:
        """Return this object for use in a context manager.

        Returns:
            This object.
        """
        return self

    def __exit__(self, *_: object) -> None:
        """Close resources when the context manager exits."""
        self.close()


class AsyncByteStream(_ByteStreamBase):
    """An asynchronous single-consumer streaming response body."""

    def __aiter__(self) -> AsyncIterator[bytes]:
        """Claim the body and return its single-consumer iterator.

        Returns:
            Single-consumer iterator over response chunks.

        Raises:
            StreamError: The stream is consumed, closed, or fails to complete.
        """
        self._claim()
        return self._consume()

    async def _consume(self) -> AsyncIterator[bytes]:
        """Yield response chunks and close the response when consumption ends.

        Raises:
            StreamError: Stream read failed.
        """
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
        """Close the response and release resources."""
        await self._response.aclose()

    async def __aenter__(self) -> Self:
        """Return this object for use in a context manager.

        Returns:
            This object.
        """
        return self

    async def __aexit__(self, *_: object) -> None:
        """Close resources when the context manager exits."""
        await self.aclose()
