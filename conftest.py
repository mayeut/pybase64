from __future__ import annotations


def pytest_addoption(parser) -> None:
    parser.addoption("--sde-cpu", action="store", default=None, help="run sde tests")
