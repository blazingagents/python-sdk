from __future__ import annotations

from collections.abc import AsyncIterator, Mapping

from ._session_models import (
    Task,
    TaskCreateResponse,
    TaskListItem,
    TaskRun,
    TaskRunMessagesPage,
    TaskRunsPage,
    TaskRunSubmission,
    TasksPage,
)
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
    TaskScheduleInput,
    Timeout,
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


def _task_schedule(schedule: TaskScheduleInput) -> dict[str, object]:
    """Convert a one-time, interval, or cron Task schedule to its wire shape."""
    return {"kind": schedule["kind"], "config": wire_fields(**schedule["config"])}


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
    body |= wire_fields(
        agent_id=agent_id,
        name=name,
        prompt=prompt,
        enabled=enabled,
        submit=submit,
        user_id=user_id,
        metadata=metadata,
    )
    if not isinstance(schedule, _Omitted):
        body["schedule"] = None if schedule is None else _task_schedule(schedule)
    return body


def _task_run_body(
    idempotency_key: str | _Omitted,
) -> dict[str, object]:
    """Build the task run request body, omitting unspecified fields."""
    if isinstance(idempotency_key, _Omitted):
        return {}
    return {"idempotencyKey": idempotency_key}


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
            decode_model(TaskCreateResponse),
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
                query=wire_fields(
                    agent_id=agent_id, user_id=user_id, cursor=cursor, limit=limit
                ),
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            decode_model(TasksPage),
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
            decode_model(Task),
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
        return await self._transport.request(
            _Request(
                "PATCH",
                _task_path(task_id),
                json_body=body,
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            decode_model(Task),
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
            decode_none,
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
            decode_model(TaskRunSubmission),
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
                query=wire_fields(cursor=cursor, limit=limit),
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            decode_model(TaskRunsPage),
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
            decode_model(TaskRun),
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
                query=wire_fields(cursor=cursor, after=after, limit=limit),
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            decode_model(TaskRunMessagesPage),
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
            decode_none,
        )
