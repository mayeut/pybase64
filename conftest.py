def pytest_addoption(parser) -> None:
    parser.addoption("--sde-cpu", action="store", default=None, help="run sde tests")
