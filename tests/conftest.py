import gc
from datetime import UTC, datetime

import pytest

from agenteng.config import Settings
from agenteng.service import Service


@pytest.fixture
def service():
    return Service(Settings(), clock=lambda: datetime(2026, 10, 4, 12, tzinfo=UTC))


@pytest.hookimpl(trylast=True)
def pytest_unconfigure(config):
    """Collect garbage while every module is still alive, then freeze what is left.

    On Python 3.12 the protobuf upb extension (pulled in by the A2A SDK) can
    segfault when the interpreter's final garbage collection runs after its
    module state is gone (protobuf only guards this on 3.13+). Collecting here,
    after all results are reported, and freezing the survivors means that final
    pass has nothing of ours to traverse. Test outcomes and the exit code are
    untouched.
    """
    gc.collect()
    gc.freeze()
