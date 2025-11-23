from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption("--sde-cpu", action="store", default=None, help="run sde tests")
