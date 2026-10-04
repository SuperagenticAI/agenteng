from datetime import UTC, datetime

import pytest

from agenteng.config import Settings
from agenteng.service import Service


@pytest.fixture
def service():
    return Service(Settings(), clock=lambda: datetime(2026, 10, 4, 12, tzinfo=UTC))
