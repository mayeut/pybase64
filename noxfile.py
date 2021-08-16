import platform
import sys

import nox


@nox.session
def lint(session: nox.Session) -> None:
    """
    Run linters on the codebase.
    """
    session.install("pre-commit")
    session.run("pre-commit", "run", "-a")


@nox.session(python=["3.6", "3.7", "3.8", "3.9", "3.10"])
def test(session: nox.Session) -> None:
    """
    Run tests.
    """
    # make extension mandatory by exporting CIBUILDWHEEL=1
    env = {"CIBUILDWHEEL": "1"}
    if sys.platform.startswith("darwin"):
        # we don't support universal builds
        env["ARCHFLAGS"] = f"-arch {platform.machine()}"
    session.install("--use-feature=in-tree-build", ".[test]", env=env)
    session.run("pytest", "--pyargs", "pybase64")
