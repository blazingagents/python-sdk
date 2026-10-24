from __future__ import annotations

import zoneinfo
from collections.abc import Iterator

import pytest

from blazing_agents import TaskCronConfig


@pytest.fixture
def no_system_timezone_data() -> Iterator[None]:
    """A machine with no IANA database, as on Windows without the tzdata package."""
    zoneinfo.reset_tzpath([])
    zoneinfo.ZoneInfo.clear_cache()
    yield
    zoneinfo.reset_tzpath()
    zoneinfo.ZoneInfo.clear_cache()


@pytest.mark.usefixtures("no_system_timezone_data")
def test_a_cron_task_decodes_without_local_timezone_data() -> None:
    config = TaskCronConfig.model_validate(
        {"expression": "0 2 * * *", "timezone": "America/New_York"}
    )

    assert config.timezone == "America/New_York"
