import asyncio

import pytest


def run(coro):
    """Run a coroutine to completion from a sync test."""
    return asyncio.run(coro)


@pytest.fixture
def call(coro_runner=run):
    return run
