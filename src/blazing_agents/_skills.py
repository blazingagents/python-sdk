from __future__ import annotations

from collections.abc import AsyncIterator, Generator, Mapping, Sequence
from contextlib import contextmanager
from typing import Literal, get_args

from ._models import Skill, SkillCopyResult, SkillCopyResults, SkillDetail, SkillsPage
from ._transport import (
    OMITTED,
    AsyncTransport,
    _Omitted,
    _Request,
    decode_bytes,
    decode_model,
    decode_none,
    path_segment,
    wire_fields,
)
from ._types import (
    SkillArchiveType,
    Timeout,
    UploadFile,
)
from ._wire import agent_path, upload_part

_SkillCopyResultList = list[SkillCopyResult]


def _skill_path(agent_id: str, skill_id: str | None = None) -> str:
    """Build the encoded skill endpoint path."""
    path = f"{agent_path(agent_id)}/skills"
    if skill_id is None:
        return path
    return f"{path}/{path_segment('skill_id', skill_id)}"


@contextmanager
def _skill_upload_request(
    *,
    agent_id: str,
    archive_type: SkillArchiveType,
    file: UploadFile,
    filename: str | None,
    extra_headers: Mapping[str, str] | None,
    timeout: Timeout | _Omitted,
) -> Generator[_Request]:
    """Build a multipart Skill upload request."""
    if archive_type not in get_args(SkillArchiveType):
        msg = "archive_type must be zip, tar, or tar.gz"
        raise ValueError(msg)
    with upload_part(
        file,
        filename=filename,
        content_type=None,
        fallback_filename=f"skill.{archive_type}",
    ) as file_part:
        multipart: dict[str, object] = {
            "type": (None, archive_type),
            **file_part,
        }
        yield _Request(
            "POST",
            f"{_skill_path(agent_id)}/upload",
            files=multipart,
            extra_headers=extra_headers,
            timeout=timeout,
        )


class AsyncAgentSkillsResource:
    def __init__(self, transport: AsyncTransport, agent_id: str) -> None:
        """Bind Skill operations to the transport.

        Args:
            transport: Transport used for requests.
            agent_id: Agent identifier.
        """
        self._transport = transport
        self._agent_id = agent_id

    async def create(
        self,
        *,
        path: Literal["SKILL.md"],
        content: str,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> SkillDetail:
        """Create a Skill.

        Args:
            path: Path to the requested file.
            content: UTF-8 Skill document or file contents.
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Returns:
            Skill details and file listing.

        Raises:
            APIStatusError: The API returns a non-success status.
            APIConnectionError: The HTTP request fails before a complete response.
            APITimeoutError: The HTTP request times out.
        """
        if path != "SKILL.md":
            msg = "path must be SKILL.md"
            raise ValueError(msg)
        return await self._transport.request(
            _Request(
                "POST",
                _skill_path(self._agent_id),
                json_body={"path": path, "content": content},
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            decode_model(SkillDetail),
        )

    async def upload(
        self,
        *,
        archive_type: SkillArchiveType,
        file: UploadFile,
        filename: str | None = None,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> SkillDetail:
        """Upload a Skill archive.

        Paths are opened and closed by the SDK. Caller-owned file objects remain
        open.

        Args:
            archive_type: Archive format: zip, tar, or tar.gz.
            file: File upload input.
            filename: Filename supplied for the upload.
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Returns:
            Skill details and file listing.

        Raises:
            ValueError: The archive format is unsupported.
            APIStatusError: The API returns a non-success status.
            APIConnectionError: The HTTP request fails before a complete response.
            APITimeoutError: The HTTP request times out.
        """
        with _skill_upload_request(
            agent_id=self._agent_id,
            archive_type=archive_type,
            file=file,
            filename=filename,
            extra_headers=extra_headers,
            timeout=timeout,
        ) as request:
            return await self._transport.request(request, decode_model(SkillDetail))

    async def list(
        self,
        *,
        cursor: str | _Omitted = OMITTED,
        limit: int | _Omitted = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> SkillsPage:
        """Fetch one page of Skill records.

        Args:
            cursor: Continuation cursor from a previous page.
            limit: Maximum number of items per page.
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
                _skill_path(self._agent_id),
                query=wire_fields(cursor=cursor, limit=limit),
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            decode_model(SkillsPage),
        )

    async def iter(
        self,
        *,
        cursor: str | _Omitted = OMITTED,
        limit: int | _Omitted = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> AsyncIterator[Skill]:
        """Iterate Skill records across all pages.

        Pages are fetched lazily. limit controls each page, not the total.

        Args:
            cursor: Continuation cursor from a previous page.
            limit: Maximum number of items per page.
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Yields:
            Skill records in server order.
        """
        next_cursor = cursor
        while True:
            page = await self.list(
                cursor=next_cursor,
                limit=limit,
                extra_headers=extra_headers,
                timeout=timeout,
            )
            for skill in page.data:
                yield skill
            if page.next_cursor is None:
                return
            next_cursor = page.next_cursor

    async def get(
        self,
        *,
        skill_id: str,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> SkillDetail:
        """Fetch the requested Skill.

        Args:
            skill_id: Skill identifier.
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Returns:
            Skill details and file listing.

        Raises:
            APIStatusError: The API returns a non-success status.
            APIConnectionError: The HTTP request fails before a complete response.
            APITimeoutError: The HTTP request times out.
        """
        return await self._transport.request(
            _Request(
                "GET",
                _skill_path(self._agent_id, skill_id),
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            decode_model(SkillDetail),
        )

    async def delete(
        self,
        *,
        skill_id: str,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> None:
        """Delete the requested Skill.

        Args:
            skill_id: Skill identifier.
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
                _skill_path(self._agent_id, skill_id),
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            decode_none,
        )

    async def read_file(
        self,
        *,
        skill_id: str,
        path: str,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> bytes:
        """Read a file within an attached Skill.

        Args:
            skill_id: Skill identifier.
            path: Path to the requested file.
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Returns:
            Downloaded response bytes.

        Raises:
            APIStatusError: The API returns a non-success status.
            APIConnectionError: The HTTP request fails before a complete response.
            APITimeoutError: The HTTP request times out.
        """
        return await self._transport.request(
            _Request(
                "GET",
                f"{_skill_path(self._agent_id, skill_id)}/files",
                query={"path": path},
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            decode_bytes,
        )

    async def replace_file(
        self,
        *,
        skill_id: str,
        path: str,
        content: bytes,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> SkillDetail:
        """Replace a file within an attached Skill.

        Args:
            skill_id: Skill identifier.
            path: Path to the requested file.
            content: Raw file bytes.
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Returns:
            Skill details and file listing.

        Raises:
            APIStatusError: The API returns a non-success status.
            APIConnectionError: The HTTP request fails before a complete response.
            APITimeoutError: The HTTP request times out.
        """
        return await self._transport.request(
            _Request(
                "PUT",
                f"{_skill_path(self._agent_id, skill_id)}/files",
                query={"path": path},
                content=content,
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            decode_model(SkillDetail),
        )

    async def delete_file(
        self,
        *,
        skill_id: str,
        path: str,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> SkillDetail:
        """Delete a file within an attached Skill.

        Args:
            skill_id: Skill identifier.
            path: Path to the requested file.
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Returns:
            Skill details and file listing.

        Raises:
            APIStatusError: The API returns a non-success status.
            APIConnectionError: The HTTP request fails before a complete response.
            APITimeoutError: The HTTP request times out.
        """
        return await self._transport.request(
            _Request(
                "DELETE",
                f"{_skill_path(self._agent_id, skill_id)}/files",
                query={"path": path},
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            decode_model(SkillDetail),
        )

    async def copy(
        self,
        *,
        skill_id: str,
        destination_agent_ids: Sequence[str],
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> _SkillCopyResultList:
        """Copy Skills to another Agent.

        Args:
            skill_id: Skill identifier.
            destination_agent_ids: Agents that receive a copy of the Skill.
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Returns:
            Per-destination copy results.

        Raises:
            APIStatusError: The API returns a non-success status.
            APIConnectionError: The HTTP request fails before a complete response.
            APITimeoutError: The HTTP request times out.
        """
        response = await self._transport.request(
            _Request(
                "POST",
                f"{_skill_path(self._agent_id, skill_id)}/copies",
                json_body={"agentIds": list(destination_agent_ids)},
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            decode_model(SkillCopyResults),
        )
        return response.root
