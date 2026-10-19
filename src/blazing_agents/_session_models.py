from __future__ import annotations

import re
from calendar import monthrange
from typing import Annotated, Literal, TypeAlias, cast
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import (
    AfterValidator,
    AnyUrl,
    AwareDatetime,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
)

from ._models import (
    AgentConfig,
    AgentId,
    ArtifactFilename,
    ArtifactId,
    MediaType,
    NonEmptyString,
    ResponseModel,
    SessionId,
    TaskId,
    TaskRunId,
    TenantId,
    ToolExecutionReference,
    TurnId,
)
from ._types import (
    SessionActivityState,
    SessionInputReason,
    SessionInputState,
)

_NUMERIC_CRON = re.compile(r"^[0-9*,/\-\s]+$")
_IANA_TIMEZONE = re.compile(
    r"^(?:UTC|[A-Za-z_]+/[A-Za-z0-9_+-]+(?:/[A-Za-z0-9_+-]+)?)$"
)
_CRON_RANGES = ((0, 59), (0, 23), (1, 31), (1, 12), (0, 7))
_CRON_STEP_MAXIMA = (60, 24, 31, 12, 7)


def _cron_values(
    value: str,
    minimum: int,
    maximum: int,
    step_maximum: int,
) -> set[int] | None:
    """Expand cron field values and validate their bounds."""
    values: set[int] = set()
    for item in value.split(","):
        base, separator, step = item.partition("/")
        if separator and (not step.isdigit() or int(step) < 1):
            return None
        stride = int(step) if separator else 1
        endpoints = base.split("-")
        if base == "*":
            lower, upper = minimum, maximum
        elif len(endpoints) > 2 or not all(part.isdigit() for part in endpoints):
            return None
        else:
            numbers = [int(part) for part in endpoints]
            if any(number < minimum or number > maximum for number in numbers):
                return None
            if len(numbers) == 2 and numbers[0] > numbers[1]:
                return None
            if separator and len(numbers) == 1:
                return None
            lower = upper = numbers[0]
            if len(numbers) == 2:
                upper = numbers[1]
        if separator and stride > step_maximum:
            return None
        values.update(range(lower, upper + 1, stride))
    return values


def _validate_cron(expression: str) -> str:
    """Return a five-field numeric cron expression, or raise ValueError."""
    fields = expression.split()
    invalid = (
        not expression.strip()
        or len(expression) > 120
        or _NUMERIC_CRON.fullmatch(expression) is None
        or len(fields) != 5
    )
    parsed_fields = (
        []
        if invalid
        else [
            _cron_values(field, *bounds, step_maximum)
            for field, bounds, step_maximum in zip(
                fields, _CRON_RANGES, _CRON_STEP_MAXIMA, strict=True
            )
        ]
    )
    if not invalid and all(values is not None for values in parsed_fields):
        days = cast(set[int], parsed_fields[2])
        months = cast(set[int], parsed_fields[3])
        invalid = fields[4] == "*" and not any(
            day <= monthrange(2024, month)[1] for month in months for day in days
        )
    else:
        invalid = True
    if invalid:
        msg = "cron schedule expression must be a valid five-field numeric cron"
        raise ValueError(msg)
    return expression


def _validate_timezone(timezone: str) -> str:
    """Validate an IANA timezone name."""
    timezone = timezone.strip()
    if len(timezone) > 64 or _IANA_TIMEZONE.fullmatch(timezone) is None:
        msg = "cron schedule timezone must be a canonical IANA timezone"
        raise ValueError(msg)
    try:
        ZoneInfo(timezone)
    except (ValueError, ZoneInfoNotFoundError) as error:
        msg = "cron schedule timezone is unknown"
        raise ValueError(msg) from error
    return timezone


class Artifact(ResponseModel):
    artifact_id: ArtifactId = Field(alias="artifactId")
    agent_id: AgentId = Field(alias="agentId")
    tenant_id: TenantId = Field(alias="tenantId")
    session_id: SessionId = Field(alias="sessionId")
    filename: ArtifactFilename
    media_type: MediaType = Field(alias="mediaType")
    size_bytes: int = Field(alias="sizeBytes", ge=0, le=10 * 1024 * 1024)
    user_id: str = Field(alias="userId")
    metadata: dict[str, object]
    created_at: AwareDatetime = Field(alias="createdAt")
    updated_at: AwareDatetime = Field(alias="updatedAt")


class ArtifactsPage(ResponseModel):
    data: list[Artifact]
    next_cursor: str | None = Field(alias="nextCursor")


class Session(ResponseModel):
    id: SessionId
    message_count: int = Field(alias="messageCount", ge=0)
    last_message_preview: str | None = Field(alias="lastMessagePreview")
    user_id: str = Field(alias="userId")
    metadata: dict[str, object]
    created_at: AwareDatetime = Field(alias="createdAt")
    updated_at: AwareDatetime = Field(alias="updatedAt")


class SessionForkedFrom(ResponseModel):
    session_id: SessionId = Field(alias="sessionId")
    message_id: NonEmptyString = Field(alias="messageId")


class SessionResponse(Session):
    agent_config: AgentConfig = Field(alias="agentConfig")
    forked_from: SessionForkedFrom | None = Field(alias="forkedFrom")


class SessionsPage(ResponseModel):
    data: list[Session]
    next_cursor: str | None = Field(alias="nextCursor")


class LatestSessionListItem(Session):
    """Latest Session with the Agent's current configuration and status."""

    agent_id: AgentId = Field(alias="agentId")
    model: NonEmptyString | None
    thinking_level: NonEmptyString | None = Field(alias="thinkingLevel")
    status: NonEmptyString


class LatestSessionsPage(ResponseModel):
    data: list[LatestSessionListItem]
    next_cursor: str | None = Field(alias="nextCursor")


class SessionMessagePart(ResponseModel):
    type: NonEmptyString


class SessionMessage(ResponseModel):
    branchable: bool
    id: NonEmptyString
    role: Literal["system", "user", "assistant"]
    parts: list[SessionMessagePart] = Field(min_length=1)
    metadata: object | None = None


class SessionMessagesPage(ResponseModel):
    data: list[SessionMessage]
    next_cursor: str | None = Field(alias="nextCursor")
    latest_cursor: str | None = Field(alias="latestCursor")


def _not_dot_segment(value: str) -> str:
    """Reject identity values that URL normalization would collapse.

    Raises:
        ValueError: requestId must not be a URL dot segment.
    """
    if value in {".", ".."}:
        raise ValueError("requestId must not be a URL dot segment.")
    return value


class SessionInputMessage(ResponseModel):
    id: NonEmptyString
    role: Literal["user"]
    parts: list[SessionMessagePart] = Field(min_length=1)
    metadata: object | None = None


class SessionActivity(ResponseModel):
    """The current Turn activity, including approval waits."""

    model_config = ConfigDict(extra="ignore")

    state: SessionActivityState
    turn_id: TurnId | None = Field(alias="turnId")


class SessionInput(ResponseModel):
    """A steer receipt bound to one Turn.

    Committed proves durable history inclusion. A not_placed message may be
    sent through ordinary chat. Never replay uncertain messages automatically.
    """

    model_config = ConfigDict(extra="ignore")

    request_id: Annotated[
        str,
        StringConstraints(min_length=1, max_length=128),
        AfterValidator(_not_dot_segment),
    ] = Field(alias="requestId")
    sequence: int = Field(ge=1)
    message: SessionInputMessage
    state: SessionInputState
    turn_id: TurnId = Field(alias="turnId")
    created_at: AwareDatetime = Field(alias="createdAt")
    updated_at: AwareDatetime = Field(alias="updatedAt")
    reason: SessionInputReason | None


class ChatSteerConsumedData(ResponseModel):
    model_config = ConfigDict(extra="ignore")

    request_id: Annotated[
        str,
        StringConstraints(min_length=1, max_length=128),
        AfterValidator(_not_dot_segment),
    ] = Field(alias="requestId")
    turn_id: TurnId = Field(alias="turnId")
    sequence: int = Field(ge=1)
    message: SessionInputMessage


class ChatSteerConsumedEvent(ResponseModel):
    """Provisional placement of a steer, before durable history commit."""

    model_config = ConfigDict(extra="ignore")

    type: Literal["data-ba-steer-consumed"]
    transient: Literal[True]
    data: ChatSteerConsumedData


class SessionInputResponse(ResponseModel):
    data: SessionInput
    activity: SessionActivity


class SessionInputsPage(ResponseModel):
    data: list[SessionInput]
    next_cursor: str | None = Field(alias="nextCursor")
    activity: SessionActivity


class SessionStopResponse(ResponseModel):
    stopped_turn_id: TurnId = Field(alias="stoppedTurnId")
    activity: SessionActivity


class TaskOnceConfig(ResponseModel):
    at: AwareDatetime


class TaskIntervalConfig(ResponseModel):
    every_ms: int = Field(alias="everyMs", ge=60_000)


class TaskCronConfig(ResponseModel):
    expression: NonEmptyString
    stagger_ms: int | None = Field(default=None, alias="staggerMs", ge=0)
    timezone: NonEmptyString

    @field_validator("expression")
    @classmethod
    def _validate_expression(cls, value: str) -> str:
        """Validate the cron expression."""
        return _validate_cron(value)

    @field_validator("timezone")
    @classmethod
    def _validate_timezone(cls, value: str) -> str:
        """Validate an IANA timezone name."""
        return _validate_timezone(value)


class TaskOnceSchedule(ResponseModel):
    kind: Literal["once"]
    config: TaskOnceConfig


class TaskIntervalSchedule(ResponseModel):
    kind: Literal["interval"]
    config: TaskIntervalConfig


class TaskCronSchedule(ResponseModel):
    kind: Literal["cron"]
    config: TaskCronConfig


TaskSchedule: TypeAlias = Annotated[
    TaskOnceSchedule | TaskIntervalSchedule | TaskCronSchedule,
    Field(discriminator="kind"),
]


class Task(ResponseModel):
    id: TaskId
    tenant_id: TenantId = Field(alias="tenantId")
    agent_id: AgentId = Field(alias="agentId")
    name: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=80),
    ]
    prompt: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=6_000),
    ]
    schedule: TaskSchedule | None
    enabled: bool
    active_run_id: TaskRunId | None = Field(alias="activeRunId")
    latest_run_id: TaskRunId | None = Field(alias="latestRunId")
    next_fire_at: AwareDatetime | None = Field(alias="nextFireAt")
    user_id: str = Field(alias="userId")
    metadata: dict[str, object]
    deleted_at: AwareDatetime | None = Field(alias="deletedAt")
    created_at: AwareDatetime = Field(alias="createdAt")
    updated_at: AwareDatetime = Field(alias="updatedAt")


TaskRunStatus: TypeAlias = Literal[
    "queued", "running", "blocked", "succeeded", "failed", "canceled"
]


class TaskLatestRun(ResponseModel):
    id: TaskRunId
    status: TaskRunStatus
    finished_at: AwareDatetime | None = Field(alias="finishedAt")


class TaskListItem(Task):
    latest_run: TaskLatestRun | None = Field(alias="latestRun")


class TasksPage(ResponseModel):
    data: list[TaskListItem]
    next_cursor: str | None = Field(alias="nextCursor")


class TaskCreateResponse(ResponseModel):
    task: Task
    run_id: TaskRunId | None = Field(alias="runId")


class TaskRunSubmission(ResponseModel):
    run_id: TaskRunId = Field(alias="runId")


class TaskRun(ResponseModel):
    id: TaskRunId
    task_id: TaskId = Field(alias="taskId")
    tenant_id: TenantId = Field(alias="tenantId")
    agent_id: AgentId = Field(alias="agentId")
    agent_config: AgentConfig = Field(alias="agentConfig")
    session_id: SessionId | None = Field(alias="sessionId")
    turn_id: TurnId | None = Field(alias="turnId")
    status: TaskRunStatus
    error: str | None
    error_code: str | None = Field(alias="errorCode")
    user_id: str = Field(alias="userId")
    metadata: dict[str, object]
    started_at: AwareDatetime | None = Field(alias="startedAt")
    finished_at: AwareDatetime | None = Field(alias="finishedAt")
    cancel_requested_at: AwareDatetime | None = Field(alias="cancelRequestedAt")
    canceled_at: AwareDatetime | None = Field(alias="canceledAt")
    created_at: AwareDatetime = Field(alias="createdAt")
    updated_at: AwareDatetime = Field(alias="updatedAt")


class TaskRunsPage(ResponseModel):
    data: list[TaskRun]
    next_cursor: str | None = Field(alias="nextCursor")


class TaskRunMessagesPage(SessionMessagesPage):
    status: TaskRunStatus
    error: str | None
    finished_at: AwareDatetime | None = Field(alias="finishedAt")


class ToolApproval(ResponseModel):
    tool: ToolExecutionReference | None = None
    assistant_message_id: NonEmptyString | None = Field(
        default=None, alias="assistantMessageId"
    )
    created_at: AwareDatetime | None = Field(default=None, alias="createdAt")
    decided_at: AwareDatetime | None = Field(default=None, alias="decidedAt")

    @field_validator("assistant_message_id", "created_at")
    @classmethod
    def _reject_explicit_null(cls, value: object) -> object:
        """Reject null assistant_message_id and created_at response fields.

        Raises:
            ValueError: Field may be omitted but cannot be null
        """
        if value is None:
            raise ValueError("Field may be omitted but cannot be null")
        return value

    approval_id: NonEmptyString = Field(alias="approvalId")
    tool_name: NonEmptyString = Field(alias="toolName")
    tool_call_id: NonEmptyString = Field(alias="toolCallId")
    input: object
    decision: Literal["pending", "approved", "denied"]
    reason: str | None


class ToolApprovalContinuation(ResponseModel):
    id: NonEmptyString
    state: Literal["waiting", "running", "succeeded", "failed"]


class ToolApprovals(ResponseModel):
    data: list[ToolApproval]
    continuation: ToolApprovalContinuation | None


class ArtifactDownloadUrl(ResponseModel):
    url: AnyUrl
    expires_at: AwareDatetime = Field(alias="expiresAt")
