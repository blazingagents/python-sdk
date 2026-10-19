from __future__ import annotations

import mimetypes
from collections.abc import Generator
from contextlib import contextmanager
from os import PathLike
from pathlib import Path

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

from ._transport import (
    path_segment,
    wire_fields,
)
from ._types import (
    SpendingLimitInput,
    UploadFile,
)


def spending_limit_body(
    spending_limit: SpendingLimitInput | None,
) -> dict[str, object]:
    return {
        "spendingLimit": None
        if spending_limit is None
        else wire_fields(**spending_limit)
    }


def agent_path(agent_id: str) -> str:
    """Build the encoded agent endpoint path."""
    return f"/v1/agents/{path_segment('agent_id', agent_id)}"


class WireInput(BaseModel):
    """Caller input validated by its snake_case names, sent with camelCase names."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        extra="forbid",
        strict=True,
        validate_by_name=True,
        validate_by_alias=False,
    )


@contextmanager
def upload_part(
    file: UploadFile,
    *,
    filename: str | None,
    content_type: str | None,
    fallback_filename: str | None = None,
) -> Generator[dict[str, tuple[str, object, str]]]:
    """Open or normalize an upload part and close owned file handles."""
    opened = None
    source_name: str | None = None
    if isinstance(file, bytes):
        content: object = file
    elif isinstance(file, (str, PathLike)):
        path = Path(file)
        opened = path.open("rb")
        content = opened
        source_name = path.name
    else:
        content = file
        raw_name = getattr(file, "name", None)
        if isinstance(raw_name, str):
            source_name = Path(raw_name).name

    upload_name = filename or source_name or fallback_filename
    if not upload_name:
        msg = "filename is required for bytes and unnamed file objects"
        raise ValueError(msg)
    upload_type = content_type or mimetypes.guess_type(upload_name)[0]
    try:
        yield {
            "file": (
                upload_name,
                content,
                upload_type or "application/octet-stream",
            )
        }
    finally:
        if opened is not None:
            opened.close()
