from __future__ import annotations

from collections.abc import AsyncIterator, Mapping

from ._session_models import Artifact, ArtifactDownloadUrl, ArtifactsPage
from ._transport import (
    OMITTED,
    AsyncTransport,
    _Omitted,
    _Request,
    decode_model,
    decode_none,
    path_segment,
    wire_fields,
)
from ._types import (
    Timeout,
)


def _artifact_path(artifact_id: str) -> str:
    """Build the encoded artifact endpoint path."""
    return f"/v1/artifacts/{path_segment('artifact_id', artifact_id)}"


class AsyncArtifactsResource:
    def __init__(self, transport: AsyncTransport) -> None:
        """Bind Artifact operations to the transport.

        Args:
            transport: Transport used for requests.
        """
        self._transport = transport

    async def list(
        self,
        *,
        agent_id: str | _Omitted = OMITTED,
        session_id: str | _Omitted = OMITTED,
        cursor: str | _Omitted = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> ArtifactsPage:
        """Fetch one page of Artifact records.

        Args:
            agent_id: Agent identifier.
            session_id: Session identifier.
            cursor: Continuation cursor from a previous page.
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Returns:
            One page of matching records and its continuation cursor.

        Raises:
            APIStatusError: The API returns a non-success status.
            APIConnectionError: The HTTP request fails before a complete response.
            APITimeoutError: The HTTP request times out.
        """
        return await self._transport.request(
            _Request(
                "GET",
                "/v1/artifacts",
                query=wire_fields(
                    agent_id=agent_id, session_id=session_id, cursor=cursor
                ),
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            decode_model(ArtifactsPage),
        )

    async def iter(
        self,
        *,
        agent_id: str | _Omitted = OMITTED,
        session_id: str | _Omitted = OMITTED,
        cursor: str | _Omitted = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> AsyncIterator[Artifact]:
        """Iterate Artifact records across all pages.

        Pages are fetched lazily until the API returns no continuation cursor.

        Args:
            agent_id: Agent identifier.
            session_id: Session identifier.
            cursor: Continuation cursor from a previous page.
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Yields:
            Artifact records in server order.
        """
        next_cursor = cursor
        while True:
            page = await self.list(
                agent_id=agent_id,
                session_id=session_id,
                cursor=next_cursor,
                extra_headers=extra_headers,
                timeout=timeout,
            )
            for artifact in page.data:
                yield artifact
            if page.next_cursor is None:
                return
            next_cursor = page.next_cursor

    async def create_download_url(
        self,
        *,
        artifact_id: str,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> ArtifactDownloadUrl:
        """Create an expiring Artifact download URL.

        Args:
            artifact_id: Artifact identifier.
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Returns:
            Expiring URL for downloading the Artifact.

        Raises:
            APIStatusError: The API returns a non-success status.
            APIConnectionError: The HTTP request fails before a complete response.
            APITimeoutError: The HTTP request times out.
        """
        return await self._transport.request(
            _Request(
                "POST",
                f"{_artifact_path(artifact_id)}/download-url",
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            decode_model(ArtifactDownloadUrl),
        )

    async def get(
        self,
        *,
        artifact_id: str,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> Artifact:
        """Fetch the requested Artifact.

        Args:
            artifact_id: Artifact identifier.
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Returns:
            Requested Artifact details.

        Raises:
            APIStatusError: The API returns a non-success status.
            APIConnectionError: The HTTP request fails before a complete response.
            APITimeoutError: The HTTP request times out.
        """
        return await self._transport.request(
            _Request(
                "GET",
                _artifact_path(artifact_id),
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            decode_model(Artifact),
        )

    async def delete(
        self,
        *,
        artifact_id: str,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> None:
        """Delete the requested Artifact.

        Args:
            artifact_id: Artifact identifier.
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Raises:
            APIStatusError: The API returns a non-success status.
            APIConnectionError: The HTTP request fails before a complete response.
            APITimeoutError: The HTTP request times out.
        """
        return await self._transport.request(
            _Request(
                "DELETE",
                _artifact_path(artifact_id),
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            decode_none,
        )
