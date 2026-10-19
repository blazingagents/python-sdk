from __future__ import annotations

import re
from collections.abc import AsyncIterator, Iterator, Mapping
from datetime import datetime
from typing import Annotated, Literal

from pydantic import AfterValidator, ConfigDict, Field, TypeAdapter

from ._models import (
    Task,
    TaskCreateResponse,
    TaskListItem,
    TaskRun,
    TaskRunMessagesPage,
    TaskRunsPage,
    TaskRunSubmission,
    TasksPage,
    _validate_cron,
    _validate_timezone,
)
from ._transport import (
    OMITTED,
    AsyncTransport,
    SyncTransport,
    _Omitted,
    _Request,
    drop_omitted,
    path_segment,
)
from ._types import (
    TaskScheduleInput,
    Timeout,
)
from ._wire import WireInput, cursor_limit_query, session_messages_query

_ISO_OFFSET_DATETIME = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$"
)


def _task_path(task_id: str | None = None) -> str:
    """Build the encoded task endpoint path."""
    path = "/v1/tasks"
    if task_id is None:
        return path
    return f"{path}/{path_segment('task_id', task_id)}"


def _task_run_path(task_id: str, run_id: str | None = None) -> str:
    """Build the encoded task run endpoint path."""
    path = f"{_task_path(task_id)}/runs"
    if run_id is None:
        return path
    return f"{path}/{path_segment('run_id', run_id)}"


def _validate_offset_datetime(value: str) -> str:
    """Return an ISO datetime with a timezone offset, or raise ValueError."""
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        parsed = None
    if (
        _ISO_OFFSET_DATETIME.fullmatch(value) is None
        or parsed is None
        or parsed.utcoffset() is None
    ):
        msg = "once schedule at must be an ISO datetime with an offset"
        raise ValueError(msg)
    return value


class _TaskOnceConfigInput(WireInput):
    at: Annotated[str, AfterValidator(_validate_offset_datetime)]


class _TaskIntervalConfigInput(WireInput):
    every_ms: int = Field(ge=60_000)


class _TaskCronConfigInput(WireInput):
    expression: Annotated[str, AfterValidator(_validate_cron)]
    timezone: Annotated[str, AfterValidator(_validate_timezone)] | None = None
    stagger_ms: int | None = Field(default=None, ge=0)


class _TaskOnceScheduleInput(WireInput):
    kind: Literal["once"]
    config: _TaskOnceConfigInput


class _TaskIntervalScheduleInput(WireInput):
    kind: Literal["interval"]
    config: _TaskIntervalConfigInput


class _TaskCronScheduleInput(WireInput):
    kind: Literal["cron"]
    config: _TaskCronConfigInput


_TASK_SCHEDULE: TypeAdapter[
    _TaskOnceScheduleInput | _TaskIntervalScheduleInput | _TaskCronScheduleInput
] = TypeAdapter(
    Annotated[
        _TaskOnceScheduleInput | _TaskIntervalScheduleInput | _TaskCronScheduleInput,
        Field(discriminator="kind"),
    ],
    config=ConfigDict(title="schedule"),
)


def _task_schedule(schedule: TaskScheduleInput) -> dict[str, object]:
    """Validate a one-time, interval, or cron Task schedule into its wire shape."""
    return _TASK_SCHEDULE.validate_python(schedule).model_dump(
        by_alias=True, exclude_none=True
    )


def _task_body(
    *,
    agent_id: str | _Omitted,
    name: str | _Omitted,
    prompt: str | _Omitted,
    schedule: TaskScheduleInput | None | _Omitted,
    enabled: bool | _Omitted,
    submit: bool | _Omitted,
    user_id: str | _Omitted,
    metadata: dict[str, object] | _Omitted,
    idempotency_key: str | _Omitted,
) -> dict[str, object]:
    """Build the task request body, omitting unspecified fields."""
    body: dict[str, object] = _task_run_body(idempotency_key)
    body |= drop_omitted(
        ("agentId", agent_id),
        ("name", name),
        ("prompt", prompt),
        ("enabled", enabled),
        ("submit", submit),
        ("userId", user_id),
        ("metadata", metadata),
    )
    if not isinstance(schedule, _Omitted):
        body["schedule"] = None if schedule is None else _task_schedule(schedule)
    return body


def _tasks_query(
    agent_id: str | _Omitted,
    user_id: str | _Omitted,
    cursor: str | _Omitted,
    limit: int | _Omitted,
) -> dict[str, str | int]:
    """Build the tasks query, omitting unspecified filters."""
    return drop_omitted(
        ("agentId", agent_id),
        ("userId", user_id),
        ("cursor", cursor),
        ("limit", limit),
    )


def _task_run_body(
    idempotency_key: str | _Omitted,
) -> dict[str, object]:
    """Build the task run request body, omitting unspecified fields."""
    if isinstance(idempotency_key, _Omitted):
        return {}
    if not isinstance(idempotency_key, str):
        msg = "idempotency_key must be a string"
        raise TypeError(msg)
    if not idempotency_key.strip():
        msg = "idempotency_key must not be blank"
        raise ValueError(msg)
    return {"idempotencyKey": idempotency_key}


class TasksResource:
    def __init__(self, transport: SyncTransport) -> None:
        """Bind Task operations to the transport.

        Args:
            transport: Transport used for requests.
        """
        self._transport = transport

    def create(
        self,
        *,
        agent_id: str,
        name: str,
        prompt: str,
        schedule: TaskScheduleInput | None | _Omitted = OMITTED,
        enabled: bool | _Omitted = OMITTED,
        submit: bool | _Omitted = OMITTED,
        user_id: str | _Omitted = OMITTED,
        metadata: dict[str, object] | _Omitted = OMITTED,
        idempotency_key: str | _Omitted = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> TaskCreateResponse:
        """Create a Task.

        Args:
            agent_id: Agent identifier.
            name: Task display name, 1 to 80 characters.
            prompt: Task prompt text.
            schedule: One-time, interval, or cron schedule. Intervals use
                every_ms of at least 60000. Cron timezone is optional.
                None clears the schedule. Omission leaves it unset.
            enabled: Whether the Task is enabled.
            submit: Optional initial Task Run submission.
            user_id: Caller-defined user identifier.
            metadata: Caller-defined JSON metadata.
            idempotency_key: Stable key for retrying the same create without
                creating another Task.
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Returns:
            Created Task and any submitted initial Run.

        Raises:
            TypeError: The schedule structure or field types are invalid.
            ValueError: The Task schedule, offset datetime, cron expression, or
                timezone is invalid.
            APIStatusError: The API returns a non-success status.
            APIConnectionError: The HTTP request fails before a complete response.
            APITimeoutError: The HTTP request times out.
        """
        return self._transport.request(
            _Request(
                "POST",
                _task_path(),
                json_body=_task_body(
                    agent_id=agent_id,
                    name=name,
                    prompt=prompt,
                    schedule=schedule,
                    enabled=enabled,
                    submit=submit,
                    user_id=user_id,
                    metadata=metadata,
                    idempotency_key=idempotency_key,
                ),
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            TaskCreateResponse,
        )

    def list(
        self,
        *,
        agent_id: str | _Omitted = OMITTED,
        user_id: str | _Omitted = OMITTED,
        cursor: str | _Omitted = OMITTED,
        limit: int | _Omitted = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> TasksPage:
        """Fetch one page of Task records.

        Args:
            agent_id: Agent identifier.
            user_id: Caller-defined user identifier.
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
        return self._transport.request(
            _Request(
                "GET",
                _task_path(),
                query=_tasks_query(agent_id, user_id, cursor, limit),
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            TasksPage,
        )

    def iter(
        self,
        *,
        agent_id: str | _Omitted = OMITTED,
        user_id: str | _Omitted = OMITTED,
        cursor: str | _Omitted = OMITTED,
        limit: int | _Omitted = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> Iterator[TaskListItem]:
        """Iterate Task records across all pages.

        Pages are fetched lazily. limit controls each page, not the total.

        Args:
            agent_id: Agent identifier.
            user_id: Caller-defined user identifier.
            cursor: Continuation cursor from a previous page.
            limit: Maximum number of items per page.
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Yields:
            TaskListItem records in server order.
        """
        next_cursor = cursor
        while True:
            page = self.list(
                agent_id=agent_id,
                user_id=user_id,
                cursor=next_cursor,
                limit=limit,
                extra_headers=extra_headers,
                timeout=timeout,
            )
            yield from page.data
            if page.next_cursor is None:
                return
            next_cursor = page.next_cursor

    def get(
        self,
        task_id: str,
        *,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> Task:
        """Fetch the requested Task.

        Args:
            task_id: Task identifier.
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Returns:
            Requested Task details.

        Raises:
            APIStatusError: The API returns a non-success status.
            APIConnectionError: The HTTP request fails before a complete response.
            APITimeoutError: The HTTP request times out.
        """
        return self._transport.request(
            _Request(
                "GET",
                _task_path(task_id),
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            Task,
        )

    def update(
        self,
        task_id: str,
        *,
        name: str | _Omitted = OMITTED,
        prompt: str | _Omitted = OMITTED,
        schedule: TaskScheduleInput | None | _Omitted = OMITTED,
        enabled: bool | _Omitted = OMITTED,
        metadata: dict[str, object] | _Omitted = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> Task:
        """Update the provided Task fields.

        Args:
            task_id: Task identifier.
            name: Task display name, 1 to 80 characters.
            prompt: Task prompt text. Omission retains the current value.
            schedule: One-time, interval, or cron schedule. Intervals use
                every_ms of at least 60000. Cron timezone is optional.
                None clears the schedule. Omission preserves it.
            enabled: Whether the Task is enabled.
            metadata: Caller-defined JSON metadata.
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Returns:
            Requested Task details.

        Raises:
            TypeError: The schedule structure or field types are invalid.
            ValueError: The Task schedule, offset datetime, cron expression, or
                timezone is invalid.
            APIStatusError: The API returns a non-success status.
            APIConnectionError: The HTTP request fails before a complete response.
            APITimeoutError: The HTTP request times out.
        """
        body = _task_body(
            agent_id=OMITTED,
            name=name,
            prompt=prompt,
            schedule=schedule,
            enabled=enabled,
            submit=OMITTED,
            user_id=OMITTED,
            metadata=metadata,
            idempotency_key=OMITTED,
        )
        if not body:
            msg = "At least one Task field must be provided."
            raise ValueError(msg)
        return self._transport.request(
            _Request(
                "PATCH",
                _task_path(task_id),
                json_body=body,
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            Task,
        )

    def delete(
        self,
        task_id: str,
        *,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> None:
        """Delete the requested Task.

        Args:
            task_id: Task identifier.
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Raises:
            APIStatusError: The API returns a non-success status.
            APIConnectionError: The HTTP request fails before a complete response.
            APITimeoutError: The HTTP request times out.
        """
        return self._transport.request(
            _Request(
                "DELETE",
                _task_path(task_id),
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            None,
        )

    def submit(
        self,
        task_id: str,
        *,
        idempotency_key: str | _Omitted = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> TaskRunSubmission:
        """Submit a Task Run for execution.

        The idempotency key is sent in the JSON body, not an HTTP header.

        Args:
            task_id: Task identifier.
            idempotency_key: Stable key for retrying the same operation without
                duplicating it.
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Returns:
            Acknowledgement of the submitted Task Run.

        Raises:
            ValueError: The idempotency key is empty or not a string.
            APIStatusError: The API returns a non-success status.
            APIConnectionError: The HTTP request fails before a complete response.
            APITimeoutError: The HTTP request times out.
        """
        return self._transport.request(
            _Request(
                "POST",
                _task_run_path(task_id),
                json_body=_task_run_body(idempotency_key),
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            TaskRunSubmission,
        )

    def list_runs(
        self,
        task_id: str,
        *,
        cursor: str | _Omitted = OMITTED,
        limit: int | _Omitted = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> TaskRunsPage:
        """Fetch one page of Task Runs.

        Args:
            task_id: Task identifier.
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
        return self._transport.request(
            _Request(
                "GET",
                _task_run_path(task_id),
                query=cursor_limit_query(cursor, limit),
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            TaskRunsPage,
        )

    def iter_runs(
        self,
        task_id: str,
        *,
        cursor: str | _Omitted = OMITTED,
        limit: int | _Omitted = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> Iterator[TaskRun]:
        """Iterate Task Runs across all pages.

        Pages are fetched lazily. limit controls each page, not the total.

        Args:
            task_id: Task identifier.
            cursor: Continuation cursor from a previous page.
            limit: Maximum number of items per page.
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Yields:
            TaskRun records in server order.
        """
        next_cursor = cursor
        while True:
            page = self.list_runs(
                task_id,
                cursor=next_cursor,
                limit=limit,
                extra_headers=extra_headers,
                timeout=timeout,
            )
            yield from page.data
            if page.next_cursor is None:
                return
            next_cursor = page.next_cursor

    def get_run(
        self,
        task_id: str,
        run_id: str,
        *,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> TaskRun:
        """Fetch a Task Run.

        Args:
            task_id: Task identifier.
            run_id: Task Run identifier.
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Returns:
            Requested Task Run details.

        Raises:
            APIStatusError: The API returns a non-success status.
            APIConnectionError: The HTTP request fails before a complete response.
            APITimeoutError: The HTTP request times out.
        """
        return self._transport.request(
            _Request(
                "GET",
                _task_run_path(task_id, run_id),
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            TaskRun,
        )

    def run_messages(
        self,
        task_id: str,
        run_id: str,
        *,
        cursor: str | _Omitted = OMITTED,
        after: str | _Omitted = OMITTED,
        limit: int | _Omitted = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> TaskRunMessagesPage:
        """Fetch a page of messages for a Task Run.

        Args:
            task_id: Task identifier.
            run_id: Task Run identifier.
            cursor: Continuation cursor from a previous page.
            after: Message cursor for fetching later messages.
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
        return self._transport.request(
            _Request(
                "GET",
                f"{_task_run_path(task_id, run_id)}/messages",
                query=session_messages_query(cursor, after, limit),
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            TaskRunMessagesPage,
        )

    def cancel_run(
        self,
        task_id: str,
        run_id: str,
        *,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> None:
        """Cancel a Task Run.

        Args:
            task_id: Task identifier.
            run_id: Task Run identifier.
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Raises:
            APIStatusError: The API returns a non-success status.
            APIConnectionError: The HTTP request fails before a complete response.
            APITimeoutError: The HTTP request times out.
        """
        return self._transport.request(
            _Request(
                "POST",
                f"{_task_run_path(task_id, run_id)}/cancel",
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            None,
        )


class AsyncTasksResource:
    def __init__(self, transport: AsyncTransport) -> None:
        """Bind Task operations to the transport.

        Args:
            transport: Transport used for requests.
        """
        self._transport = transport

    async def create(
        self,
        *,
        agent_id: str,
        name: str,
        prompt: str,
        schedule: TaskScheduleInput | None | _Omitted = OMITTED,
        enabled: bool | _Omitted = OMITTED,
        submit: bool | _Omitted = OMITTED,
        user_id: str | _Omitted = OMITTED,
        metadata: dict[str, object] | _Omitted = OMITTED,
        idempotency_key: str | _Omitted = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> TaskCreateResponse:
        """Create a Task.

        Args:
            agent_id: Agent identifier.
            name: Task display name, 1 to 80 characters.
            prompt: Task prompt text.
            schedule: One-time, interval, or cron schedule. Intervals use
                every_ms of at least 60000. Cron timezone is optional.
                None clears the schedule. Omission leaves it unset.
            enabled: Whether the Task is enabled.
            submit: Optional initial Task Run submission.
            user_id: Caller-defined user identifier.
            metadata: Caller-defined JSON metadata.
            idempotency_key: Stable key for retrying the same create without
                creating another Task.
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Returns:
            Created Task and any submitted initial Run.

        Raises:
            TypeError: The schedule structure or field types are invalid.
            ValueError: The Task schedule, offset datetime, cron expression, or
                timezone is invalid.
            APIStatusError: The API returns a non-success status.
            APIConnectionError: The HTTP request fails before a complete response.
            APITimeoutError: The HTTP request times out.
        """
        return await self._transport.request(
            _Request(
                "POST",
                _task_path(),
                json_body=_task_body(
                    agent_id=agent_id,
                    name=name,
                    prompt=prompt,
                    schedule=schedule,
                    enabled=enabled,
                    submit=submit,
                    user_id=user_id,
                    metadata=metadata,
                    idempotency_key=idempotency_key,
                ),
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            TaskCreateResponse,
        )

    async def list(
        self,
        *,
        agent_id: str | _Omitted = OMITTED,
        user_id: str | _Omitted = OMITTED,
        cursor: str | _Omitted = OMITTED,
        limit: int | _Omitted = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> TasksPage:
        """Fetch one page of Task records.

        Args:
            agent_id: Agent identifier.
            user_id: Caller-defined user identifier.
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
                _task_path(),
                query=_tasks_query(agent_id, user_id, cursor, limit),
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            TasksPage,
        )

    async def iter(
        self,
        *,
        agent_id: str | _Omitted = OMITTED,
        user_id: str | _Omitted = OMITTED,
        cursor: str | _Omitted = OMITTED,
        limit: int | _Omitted = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> AsyncIterator[TaskListItem]:
        """Iterate Task records across all pages.

        Pages are fetched lazily. limit controls each page, not the total.

        Args:
            agent_id: Agent identifier.
            user_id: Caller-defined user identifier.
            cursor: Continuation cursor from a previous page.
            limit: Maximum number of items per page.
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Yields:
            TaskListItem records in server order.
        """
        next_cursor = cursor
        while True:
            page = await self.list(
                agent_id=agent_id,
                user_id=user_id,
                cursor=next_cursor,
                limit=limit,
                extra_headers=extra_headers,
                timeout=timeout,
            )
            for task in page.data:
                yield task
            if page.next_cursor is None:
                return
            next_cursor = page.next_cursor

    async def get(
        self,
        task_id: str,
        *,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> Task:
        """Fetch the requested Task.

        Args:
            task_id: Task identifier.
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Returns:
            Requested Task details.

        Raises:
            APIStatusError: The API returns a non-success status.
            APIConnectionError: The HTTP request fails before a complete response.
            APITimeoutError: The HTTP request times out.
        """
        return await self._transport.request(
            _Request(
                "GET",
                _task_path(task_id),
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            Task,
        )

    async def update(
        self,
        task_id: str,
        *,
        name: str | _Omitted = OMITTED,
        prompt: str | _Omitted = OMITTED,
        schedule: TaskScheduleInput | None | _Omitted = OMITTED,
        enabled: bool | _Omitted = OMITTED,
        metadata: dict[str, object] | _Omitted = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> Task:
        """Update the provided Task fields.

        Args:
            task_id: Task identifier.
            name: Task display name, 1 to 80 characters.
            prompt: Task prompt text. Omission retains the current value.
            schedule: One-time, interval, or cron schedule. Intervals use
                every_ms of at least 60000. Cron timezone is optional.
                None clears the schedule. Omission preserves it.
            enabled: Whether the Task is enabled.
            metadata: Caller-defined JSON metadata.
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Returns:
            Requested Task details.

        Raises:
            TypeError: The schedule structure or field types are invalid.
            ValueError: The Task schedule, offset datetime, cron expression, or
                timezone is invalid.
            APIStatusError: The API returns a non-success status.
            APIConnectionError: The HTTP request fails before a complete response.
            APITimeoutError: The HTTP request times out.
        """
        body = _task_body(
            agent_id=OMITTED,
            name=name,
            prompt=prompt,
            schedule=schedule,
            enabled=enabled,
            submit=OMITTED,
            user_id=OMITTED,
            metadata=metadata,
            idempotency_key=OMITTED,
        )
        if not body:
            msg = "At least one Task field must be provided."
            raise ValueError(msg)
        return await self._transport.request(
            _Request(
                "PATCH",
                _task_path(task_id),
                json_body=body,
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            Task,
        )

    async def delete(
        self,
        task_id: str,
        *,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> None:
        """Delete the requested Task.

        Args:
            task_id: Task identifier.
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
                _task_path(task_id),
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            None,
        )

    async def submit(
        self,
        task_id: str,
        *,
        idempotency_key: str | _Omitted = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> TaskRunSubmission:
        """Submit a Task Run for execution.

        The idempotency key is sent in the JSON body, not an HTTP header.

        Args:
            task_id: Task identifier.
            idempotency_key: Stable key for retrying the same operation without
                duplicating it.
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Returns:
            Acknowledgement of the submitted Task Run.

        Raises:
            ValueError: The idempotency key is empty or not a string.
            APIStatusError: The API returns a non-success status.
            APIConnectionError: The HTTP request fails before a complete response.
            APITimeoutError: The HTTP request times out.
        """
        return await self._transport.request(
            _Request(
                "POST",
                _task_run_path(task_id),
                json_body=_task_run_body(idempotency_key),
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            TaskRunSubmission,
        )

    async def list_runs(
        self,
        task_id: str,
        *,
        cursor: str | _Omitted = OMITTED,
        limit: int | _Omitted = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> TaskRunsPage:
        """Fetch one page of Task Runs.

        Args:
            task_id: Task identifier.
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
                _task_run_path(task_id),
                query=cursor_limit_query(cursor, limit),
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            TaskRunsPage,
        )

    async def iter_runs(
        self,
        task_id: str,
        *,
        cursor: str | _Omitted = OMITTED,
        limit: int | _Omitted = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> AsyncIterator[TaskRun]:
        """Iterate Task Runs across all pages.

        Pages are fetched lazily. limit controls each page, not the total.

        Args:
            task_id: Task identifier.
            cursor: Continuation cursor from a previous page.
            limit: Maximum number of items per page.
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Yields:
            TaskRun records in server order.
        """
        next_cursor = cursor
        while True:
            page = await self.list_runs(
                task_id,
                cursor=next_cursor,
                limit=limit,
                extra_headers=extra_headers,
                timeout=timeout,
            )
            for run in page.data:
                yield run
            if page.next_cursor is None:
                return
            next_cursor = page.next_cursor

    async def get_run(
        self,
        task_id: str,
        run_id: str,
        *,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> TaskRun:
        """Fetch a Task Run.

        Args:
            task_id: Task identifier.
            run_id: Task Run identifier.
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Returns:
            Requested Task Run details.

        Raises:
            APIStatusError: The API returns a non-success status.
            APIConnectionError: The HTTP request fails before a complete response.
            APITimeoutError: The HTTP request times out.
        """
        return await self._transport.request(
            _Request(
                "GET",
                _task_run_path(task_id, run_id),
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            TaskRun,
        )

    async def run_messages(
        self,
        task_id: str,
        run_id: str,
        *,
        cursor: str | _Omitted = OMITTED,
        after: str | _Omitted = OMITTED,
        limit: int | _Omitted = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> TaskRunMessagesPage:
        """Fetch a page of messages for a Task Run.

        Args:
            task_id: Task identifier.
            run_id: Task Run identifier.
            cursor: Continuation cursor from a previous page.
            after: Message cursor for fetching later messages.
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
                f"{_task_run_path(task_id, run_id)}/messages",
                query=session_messages_query(cursor, after, limit),
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            TaskRunMessagesPage,
        )

    async def cancel_run(
        self,
        task_id: str,
        run_id: str,
        *,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> None:
        """Cancel a Task Run.

        Args:
            task_id: Task identifier.
            run_id: Task Run identifier.
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
                "POST",
                f"{_task_run_path(task_id, run_id)}/cancel",
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            None,
        )
