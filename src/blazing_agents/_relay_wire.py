"""The browser-to-relay wire: request bodies, UI message checks and error answers.

The browser posts every request to one URL with a JSON body whose `op` names the
operation. `_relay.py` answers it. The contract is the TypeScript SDK's
`docs/relay-contract.md`.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Annotated, Any, Literal, cast

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    RootModel,
    ValidationError,
    field_validator,
    model_validator,
)

from ._errors import APIConnectionError, APIStatusError, StreamError
from ._models import NonEmptyString, SessionId
from ._session_models import SessionInputRequestId
from ._types import ChatTrigger, ToolApprovalDecisionInput

_LOGGER = logging.getLogger("blazing_agents")

HISTORY_PAGE_SIZE = 200


def _reject_null_options(model: type[BaseModel], data: object) -> None:
    if not isinstance(data, dict):
        return
    body = cast(dict[str, object], data)
    for name, field in model.model_fields.items():
        key = field.alias or name
        if not field.is_required() and body.get(key, "") is None:
            raise ValueError(f"{key} must be omitted, not null.")


class _Fields(BaseModel):
    """A model that rejects coerced values, ignores unknown keys and forbids null.

    An optional field is omitted, never null, as in the TypeScript relay, so every
    relay in every language answers the same bodies with 400.
    """

    model_config = ConfigDict(strict=True, extra="ignore")

    @model_validator(mode="before")
    @classmethod
    def _optional_fields_are_omitted_not_null(cls, data: Any) -> Any:
        _reject_null_options(cls, data)
        return data


class ChatBody(_Fields):
    op: Literal["chat"]
    message: object
    message_id: NonEmptyString | None = Field(default=None, alias="messageId")
    session_id: SessionId | None = Field(default=None, alias="sessionId")
    trigger: ChatTrigger = "submit-message"


class HistoryBody(_Fields):
    op: Literal["history"]
    session_id: SessionId = Field(alias="sessionId")
    cursor: NonEmptyString | None = None


class SteerBody(_Fields):
    op: Literal["steer"]
    session_id: SessionId = Field(alias="sessionId")
    request_id: SessionInputRequestId = Field(alias="requestId")
    message: object


RelayBody = ChatBody | HistoryBody | SteerBody


class _Body(RootModel[Annotated[RelayBody, Field(discriminator="op")]]):
    pass


def parse_body(raw: bytes) -> RelayBody | None:
    """Parse a request body, or return None when it breaks the contract."""
    try:
        return _Body.model_validate_json(raw).root
    except ValidationError:
        return None


class _Part(BaseModel):
    """Any message part. The relay reads the kinds below and forwards the rest."""

    model_config = ConfigDict(strict=True, extra="allow")

    type: NonEmptyString


class _TextPart(_Part):
    text: str


class _Approval(_Fields):
    id: NonEmptyString
    approved: bool
    reason: str | None = None


class _ApprovalRespondedPart(_Part):
    """A Tool part that holds the person's decision."""

    state: Literal["approval-responded"]
    tool_call_id: str = Field(alias="toolCallId")
    tool_name: str | None = Field(default=None, alias="toolName")
    input: Any
    approval: _Approval

    @model_validator(mode="after")
    def _dynamic_tools_are_named(self) -> _ApprovalRespondedPart:
        if self.type == "dynamic-tool" and self.tool_name is None:
            raise ValueError("A dynamic tool part needs a toolName.")
        return self


def _is_tool(kind: str) -> bool:
    return kind.startswith("tool-") or kind == "dynamic-tool"


def _typed_part(value: object) -> _Part:
    part = _Part.model_validate(value)
    if part.type == "text":
        return _TextPart.model_validate(value)
    extras = part.model_extra or {}
    if _is_tool(part.type) and extras.get("state") == "approval-responded":
        return _ApprovalRespondedPart.model_validate(value)
    return part


class UIMessage(BaseModel):
    """An AI SDK UI message, checked for the shape the relay relies on.

    The relay forwards a user message unchanged, and the API validates it again.
    """

    model_config = ConfigDict(strict=True, extra="allow")

    id: NonEmptyString
    role: Literal["system", "user", "assistant"]
    parts: list[_Part] = Field(min_length=1)

    @field_validator("parts", mode="before")
    @classmethod
    def _typed_parts(cls, value: object) -> object:
        if isinstance(value, list):
            return [_typed_part(part) for part in cast(list[object], value)]
        return value

    def approval_decisions(self) -> list[ToolApprovalDecisionInput]:
        """Return the decisions after the last `step-start` part."""
        last_step = max(
            (
                index
                for index, part in enumerate(self.parts)
                if part.type == "step-start"
            ),
            default=-1,
        )
        decisions: list[ToolApprovalDecisionInput] = []
        for part in self.parts[last_step + 1 :]:
            if isinstance(part, _ApprovalRespondedPart):
                decision: ToolApprovalDecisionInput = {
                    "approval_id": part.approval.id,
                    "approved": part.approval.approved,
                }
                if part.approval.reason is not None:
                    decision["reason"] = part.approval.reason
                decisions.append(decision)
        return decisions


def parse_message(value: object) -> UIMessage | None:
    """Validate a UI message, or return None when it is malformed."""
    try:
        return UIMessage.model_validate(value)
    except ValidationError:
        return None


@dataclass(frozen=True, slots=True)
class RelayFailure:
    """An error answer: `{"error": {"code", "message"}}` with its status."""

    status_code: int
    code: str
    message: str
    request_id: str | None = None

    @property
    def headers(self) -> dict[str, str]:
        return {} if self.request_id is None else {"x-request-id": self.request_id}

    @property
    def body(self) -> dict[str, object]:
        return {"error": {"code": self.code, "message": self.message}}


INVALID_REQUEST = "invalid_request"


def rejected(message: str) -> RelayFailure:
    """A 400 for a request that breaks the contract."""
    return RelayFailure(400, INVALID_REQUEST, message)


def failure_of(error: Exception) -> RelayFailure:
    """Map an SDK error to the answer the browser reads.

    An API error keeps its status, code and message. Any other failure answers 500
    without its cause, which goes to the `blazing_agents` logger instead.
    """
    if isinstance(error, APIStatusError):
        return RelayFailure(
            error.status_code, error.code, error.message, error.request_id
        )
    if isinstance(error, StreamError):
        return RelayFailure(502, "stream_error", str(error), error.request_id)
    if isinstance(error, APIConnectionError):
        return RelayFailure(502, "network_error", str(error))
    _LOGGER.error("The chat relay failed.", exc_info=error)
    return RelayFailure(500, "internal_error", "Request failed.")
