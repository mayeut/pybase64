from __future__ import annotations

TYPE_CHECKING = False
if TYPE_CHECKING:
    import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption("--sde-cpu", action="store", default=None, help="run sde tests")
    parser.addoption(
        "--pypi-distribution",
        action="store_true",
        default=False,
        help="run PyPI distribution tests",
    )
