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
        super().__init__(response)
        self._deltas: list[str] = []
        self._complete = False
        self._failure: StreamError | None = None

    def _final_text(self) -> Completion:
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
        super().__init__(response)
        self._text_iterator: Iterator[str] | None = None

    def __iter__(self) -> Iterator[str]:
        self._claim()
        self._text_iterator = self._consume_text()
        return self._text_iterator

    def _consume_text(self) -> Iterator[str]:
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
        if not self._complete and self._failure is None:
            if self._text_iterator is None:
                self._claim()
                self._text_iterator = self._consume_text()
            for _ in self._text_iterator:
                pass
        return self._final_text()

    def close(self) -> None:
        self._response.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


class AsyncCompletionStream(_CompletionStreamBase):
    """An asynchronous single-consumer stream of completion text deltas."""

    def __init__(self, response: httpx.Response) -> None:
        super().__init__(response)
        self._text_iterator: AsyncIterator[str] | None = None

    def __aiter__(self) -> AsyncIterator[str]:
        self._claim()
        self._text_iterator = self._consume_text()
        return self._text_iterator

    async def _consume_text(self) -> AsyncIterator[str]:
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
        if not self._complete and self._failure is None:
            if self._text_iterator is None:
                self._claim()
                self._text_iterator = self._consume_text()
            async for _ in self._text_iterator:
                pass
        return self._final_text()

    async def aclose(self) -> None:
        await self._response.aclose()

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.aclose()


def generation_request(
    *,
    agent_id: str,
    output: dict[str, object],
    prompt: str | _Omitted = OMITTED,
    prompt_id: str | _Omitted = OMITTED,
    variables: dict[str, str] | _Omitted = OMITTED,
    version: int | _Omitted = OMITTED,
    user_id: str | _Omitted = OMITTED,
    metadata: dict[str, object] | _Omitted = OMITTED,
    client_request_id: str | None = None,
    extra_headers: Mapping[str, str] | None = None,
    timeout: Timeout | _Omitted = OMITTED,
) -> _Request:
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
        ("version", version),
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
