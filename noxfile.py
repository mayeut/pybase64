import sys
from pathlib import Path
from typing import Dict

import nox

HERE = Path(__file__).resolve().parent


@nox.session
def lint(session: nox.Session) -> None:
    """
    Run linters on the codebase.
    """
    session.install("pre-commit")
    session.run("pre-commit", "run", "-a")


def update_env_macos(session: nox.Session, env: Dict[str, str]) -> None:
    if sys.platform.startswith("darwin"):
        # we don't support universal builds
        machine = session.run(
            "python", "-sSEc", "import platform; print(platform.machine())", silent=True
        ).strip()
        env["ARCHFLAGS"] = f"-arch {machine}"
        env["_PYTHON_HOST_PLATFORM"] = f"macosx-11.0-{machine}"


def remove_extension(session: nox.Session, in_place: bool = False) -> None:
    if in_place:
        where = HERE / "src" / "pybase64"
    else:
        command = "import sysconfig; print(sysconfig.get_path('platlib'))"
        platlib = session.run("python", "-c", command, silent=True).strip()
        where = Path(platlib) / "pybase64"
        assert where.exists()

    removed = False
    for ext in ["*.so", "*.pyd"]:
        for file in where.glob(ext):
            session.log(f"removing '{file.relative_to(HERE)}'")
            file.unlink()
            removed = True
    if not in_place:
        assert removed


@nox.session(python=["3.6", "3.7", "3.8", "3.9", "3.10"])
def test(session: nox.Session) -> None:
    """
    Run tests.
    """
    session.install("-r", "requirements-test.txt")
    # make extension mandatory by exporting CIBUILDWHEEL=1
    env = {"CIBUILDWHEEL": "1"}
    update_env_macos(session, env)
    session.install(".", env=env)
    session.run("pytest", env=env)
    # run without extension as well
    env.pop("CIBUILDWHEEL")
    remove_extension(session)
    session.run("pytest", env=env)


@nox.session
def coverage(session: nox.Session) -> None:
    with_sde = False
    if session.posargs:
        assert session.posargs == ["--with-sde"]
        with_sde = True
    coverage_args = ("--cov=pybase64", "--cov-append", "--cov-branch", "--cov-report=")
    pytest_command = ("pytest", *coverage_args)

    session.install("-r", "requirements-test.txt", "-r", "requirements-coverage.txt")
    remove_extension(session, in_place=True)
    # make extension mandatory by exporting CIBUILDWHEEL=1
    env = {
        "CIBUILDWHEEL": "1",
        "CFLAGS": "-O0 -coverage",
        "LDFLAGS": "-coverage",
        "COVERAGE_PROCESS_START": "1",
    }
    update_env_macos(session, env)
    session.install("-e", ".", env=env)
    session.run("python", "-m", "coverage", "erase", env=env)
    session.run(*pytest_command, env=env)
    if with_sde:
        session.run("sde", "--", *pytest_command, env=env, external=True)
        for cpu in ["p4p", "mrm", "pnr", "nhm", "snb", "hsw"]:
            sde = ("sde", f"-{cpu}", "--")
            pytest_addopt = (f"--sde-cpu={cpu}", "-k=test_flags")
            session.run(*sde, *pytest_command, *pytest_addopt, env=env, external=True)

    # run without extension as well
    env.pop("CIBUILDWHEEL")
    remove_extension(session, in_place=True)
    session.run(*pytest_command, env=env)

    # reports
    session.run(
        "python", "-m", "coverage", "report", "--show-missing", "--fail-under=93"
    )
    session.run(
        "gcovr", "-r=.", "-s", "-e=base64", "-e=.base64_build", "--fail-under-line=90"
    )
