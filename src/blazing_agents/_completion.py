from __future__ import annotations

from collections.abc import AsyncIterator, Iterator, Mapping
from typing import Self
from urllib.parse import quote

import httpx

from ._downloads import _ByteStreamBase
from ._errors import StreamError
from ._responses import Completion
from ._transport import OMITTED, _Omitted, _Request
from ._types import Timeout


class _CompletionStreamBase(_ByteStreamBase):
    def __init__(self, response: httpx.Response) -> None:
        """Initialize CompletionStreamBase.

        Args:
            response: HTTPX response supplying the body and response metadata.
        """
        super().__init__(response)
        self._deltas: list[str] = []
        self._complete = False
        self._failure: StreamError | None = None

    def _final_text(self) -> Completion:
        """Return buffered text after successful stream completion.

        Raises:
            StreamError: Stream did not complete successfully.
        """
        if self._failure is not None:
            raise self._failure
        if not self._complete:
            raise StreamError(
                "Stream did not complete successfully.",
                response=self._response,
            )
        return Completion("".join(self._deltas), self._response)


class CompletionStream(_CompletionStreamBase):
    """A single-consumer stream of decoded completion text deltas."""

    def __init__(self, response: httpx.Response) -> None:
        """Initialize CompletionStream.

        Args:
            response: HTTPX response supplying the body and response metadata.
        """
        super().__init__(response)
        self._text_iterator: Iterator[str] | None = None

    def __iter__(self) -> Iterator[str]:
        """Claim the body and return its single-consumer iterator.

        Returns:
            Single-consumer iterator over response chunks.

        Raises:
            StreamError: The stream is consumed, closed, or fails to complete.
        """
        self._claim()
        self._text_iterator = self._consume_text()
        return self._text_iterator

    def _consume_text(self) -> Iterator[str]:
        """Yield response chunks and close the response when consumption ends."""
        try:
            for delta in self._response.iter_text():
                self._deltas.append(delta)
                yield delta
            self._complete = True
        except httpx.HTTPError as error:
            failure = StreamError("Stream read failed.", response=self._response)
            self._failure = failure
            raise failure from error
        finally:
            self.close()

    def get_final_text(self) -> Completion:
        """Consume remaining deltas and return the complete text.

        This drains any unread deltas. Repeated calls return the buffered result.

        Returns:
            Complete buffered text with its server request_id.

        Raises:
            StreamError: The stream is consumed, closed, or fails to complete.
        """
        if not self._complete and self._failure is None:
            if self._text_iterator is None:
                self._claim()
                self._text_iterator = self._consume_text()
            for _ in self._text_iterator:
                pass
        return self._final_text()

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


class AsyncCompletionStream(_CompletionStreamBase):
    """An asynchronous single-consumer stream of completion text deltas."""

    def __init__(self, response: httpx.Response) -> None:
        """Initialize AsyncCompletionStream.

        Args:
            response: HTTPX response supplying the body and response metadata.
        """
        super().__init__(response)
        self._text_iterator: AsyncIterator[str] | None = None

    def __aiter__(self) -> AsyncIterator[str]:
        """Claim the body and return its single-consumer iterator.

        Returns:
            Single-consumer iterator over response chunks.

        Raises:
            StreamError: The stream is consumed, closed, or fails to complete.
        """
        self._claim()
        self._text_iterator = self._consume_text()
        return self._text_iterator

    async def _consume_text(self) -> AsyncIterator[str]:
        """Yield response chunks and close the response when consumption ends."""
        try:
            async for delta in self._response.aiter_text():
                self._deltas.append(delta)
                yield delta
            self._complete = True
        except httpx.HTTPError as error:
            failure = StreamError("Stream read failed.", response=self._response)
            self._failure = failure
            raise failure from error
        finally:
            await self.aclose()

    async def get_final_text(self) -> Completion:
        """Consume remaining deltas and return the complete text.

        This drains any unread deltas. Repeated calls return the buffered result.

        Returns:
            Complete buffered text with its server request_id.

        Raises:
            StreamError: The stream is consumed, closed, or fails to complete.
        """
        if not self._complete and self._failure is None:
            if self._text_iterator is None:
                self._claim()
                self._text_iterator = self._consume_text()
            async for _ in self._text_iterator:
                pass
        return self._final_text()

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


def generation_request(
    *,
    agent_id: str,
    output: dict[str, object],
    prompt: str | _Omitted = OMITTED,
    prompt_id: str | _Omitted = OMITTED,
    variables: dict[str, str] | _Omitted = OMITTED,
    user_id: str | _Omitted = OMITTED,
    metadata: dict[str, object] | _Omitted = OMITTED,
    client_request_id: str | None = None,
    extra_headers: Mapping[str, str] | None = None,
    timeout: Timeout | _Omitted = OMITTED,
) -> _Request:
    """Build a generation request with one prompt source.

    Provide exactly one of prompt or prompt_id. variables requires prompt_id.

    Args:
        agent_id: Agent identifier.
        output: Output format requested from the generation endpoint.
        prompt: Literal prompt. Provide exactly one of prompt or prompt_id.
        prompt_id: Stored Prompt identifier.
        variables: Template substitutions. Requires prompt_id.
        user_id: Caller-defined user identifier.
        metadata: Caller-defined JSON metadata.
        client_request_id: Caller correlation ID sent as X-Client-Request-Id.
        extra_headers: Headers for this request. Authorization uses the client API
            key.
        timeout: Request timeout override. OMITTED inherits the client timeout.

    Returns:
        Prepared HTTP request.

    Raises:
        ValueError: Provide exactly one of prompt or prompt_id. variables can only be
            used with prompt_id.
    """
    has_prompt = not isinstance(prompt, _Omitted)
    has_prompt_id = not isinstance(prompt_id, _Omitted)
    if has_prompt == has_prompt_id:
        raise ValueError("Provide exactly one of prompt or prompt_id.")
    if not isinstance(variables, _Omitted) and not has_prompt_id:
        raise ValueError("variables can only be used with prompt_id.")

    body: dict[str, object] = {"output": output}
    if has_prompt:
        body["prompt"] = prompt
    else:
        body["promptId"] = prompt_id
        if not isinstance(variables, _Omitted):
            body["variables"] = variables
    for wire_name, value in (
        ("userId", user_id),
        ("metadata", metadata),
    ):
        if not isinstance(value, _Omitted):
            body[wire_name] = value

    return _Request(
        "POST",
        f"/v1/agents/{quote(agent_id, safe='')}/generation",
        client_request_id=client_request_id,
        json_body=body,
        extra_headers=extra_headers,
        timeout=timeout,
    )
