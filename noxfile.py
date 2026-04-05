from __future__ import annotations

import os
import sys
from pathlib import Path

import nox

HERE = Path(__file__).resolve().parent

nox.needs_version = ">=2025.11.12"
nox.options.default_venv_backend = "uv|virtualenv"
nox.options.sessions = ["lint", "test"]

ALL_CPYTHON = [f"3.{minor}" for minor in range(9, 15 + 1)]
ALL_CPYTHONT = [f"3.{minor}t" for minor in range(13, 15 + 1)]
ALL_PYPY = [f"pypy3.{minor}" for minor in range(9, 11 + 1)]
ALL_PYTHON = ALL_CPYTHON + ALL_CPYTHONT + ALL_PYPY


def _install_dep_group(session: nox.Session, *groups: str, only_binary: bool = True) -> None:
    args = ["--no-deps", "--require-hashes"]
    if only_binary:
        args.append("--only-binary=:all:")
    args.extend(f"--requirement=requirements/{group}/requirements-ci.txt" for group in groups)
    session.install(*args)


@nox.session
def lint(session: nox.Session) -> None:
    """Run linters on the codebase."""
    _install_dep_group(session, "lint")
    session.run("prek", "run", "--all-files", *session.posargs)


def update_env_macos(session: nox.Session, env: dict[str, str]) -> None:
    if sys.platform.startswith("darwin"):
        # we don't support universal builds
        machine = session.run(  # type: ignore[union-attr]
            "python",
            "-sSEc",
            "import platform; print(platform.machine())",
            silent=True,
        ).strip()
        env["ARCHFLAGS"] = f"-arch {machine}"
        env["_PYTHON_HOST_PLATFORM"] = f"macosx-11.0-{machine}"


def remove_extension(session: nox.Session, in_place: bool = False) -> None:
    if in_place:
        where = HERE / "src" / "pybase64"
    else:
        command = "import sysconfig; print(sysconfig.get_path('platlib'))"
        platlib = session.run("python", "-c", command, silent=True).strip()  # type: ignore[union-attr]
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


@nox.session(python=ALL_PYTHON)
def test(session: nox.Session) -> None:
    """Run tests."""
    _install_dep_group(session, "build-system", "test")
    # make extension mandatory by exporting CIBUILDWHEEL=1
    env = {"CIBUILDWHEEL": "1"}
    update_env_macos(session, env)
    session.install("--no-deps", "--no-build-isolation", ".", env=env)
    session.run("pytest", *session.posargs, env=env)
    # run without extension as well
    env.pop("CIBUILDWHEEL")
    remove_extension(session)
    session.run("pytest", *session.posargs, env=env)


@nox.session(python=ALL_CPYTHONT)
def test_parallel(session: nox.Session) -> None:
    """Run tests."""
    _install_dep_group(session, "build-system", "test")
    posargs = session.posargs
    if not posargs:
        posargs = ["--parallel-threads=auto", "--iterations=32"]
    # make extension mandatory by exporting CIBUILDWHEEL=1
    env = {"CIBUILDWHEEL": "1"}
    update_env_macos(session, env)
    session.install("--no-deps", "--no-build-isolation", ".", env=env)
    session.run("pytest", *posargs, env=env)
    # run without extension as well
    env.pop("CIBUILDWHEEL")
    remove_extension(session)
    session.run("pytest", *posargs, env=env)


@nox.session(python=["3.14", "3.15", "pypy3.10", "pypy3.11"])
def _coverage(session: nox.Session) -> None:
    """Internal coverage run. Do not run manually"""
    _install_dep_group(session, "build-system", "coverage", only_binary=False)
    gcovr_config = (
        "-r=.",
        "-e=base64",
        "-e=.base64_build",
        "--gcov-exclude-directory=.base64_build",
    )
    with_sde = "--with-sde" in session.posargs
    clean = "--clean" in session.posargs
    report = "--report" in session.posargs
    coverage_args = (
        "--cov=pybase64",
        "--cov=tests",
        "--cov-append",
        "--cov-report=",
    )
    pytest_command = ("pytest", *coverage_args)
    remove_extension(session, in_place=True)
    # make extension mandatory by exporting CIBUILDWHEEL=1
    env = {
        "CIBUILDWHEEL": "1",
        "CFLAGS": "-O0 -coverage",
        "LDFLAGS": "-coverage",
    }
    update_env_macos(session, env)
    session.install("--no-deps", "--no-build-isolation", "-e", ".", env=env)
    if clean:
        session.run("coverage", "erase", env=env)
    session.run(*pytest_command, env=env)
    if with_sde:
        cpu = "spr"
        sde = ("sde64", f"-{cpu}", "--")
        session.run(*sde, *pytest_command, f"--sde-cpu={cpu}", env=env, external=True)
        for cpu in ["p4p", "mrm", "pnr", "nhm", "snb", "hsw", "skx"]:
            sde = ("sde64", f"-{cpu}", "--")
            pytest_addopt = (f"--sde-cpu={cpu}", "-k=test_flags")
            session.run(*sde, *pytest_command, *pytest_addopt, env=env, external=True)

    # run without extension as well
    env.pop("CIBUILDWHEEL")
    remove_extension(session, in_place=True)
    session.run(*pytest_command, env=env)
    session.run("gcovr", *gcovr_config, f"--json=coverage-native-{session.python}.json")

    # reports
    if report:
        threshold = 100.0 if "CI" in os.environ else 99.8
        session.run("coverage", "report", "--show-missing", f"--fail-under={threshold}")
        session.run("coverage", "xml", "-ocoverage-python.xml")
        session.run(
            "gcovr",
            *gcovr_config,
            "--add-tracefile=coverage-native-*.json",
            "--fail-under-line=89",
            "--txt",
            "--print-summary",
            "--xml=coverage-native.xml",
        )


@nox.session(venv_backend="none")
def coverage(session: nox.Session) -> None:
    """Coverage tests."""
    posargs_ = set(session.posargs)
    assert len(posargs_ & {"--clean", "--report"}) == 0
    assert len(posargs_ - {"--with-sde"}) == 0
    posargs = [*session.posargs, "--report"]
    session.notify("_coverage-pypy3.11", ["--clean"])
    session.notify("_coverage-pypy3.10", [])
    session.notify("_coverage-3.15", [])
    session.notify("_coverage-3.14", posargs)


@nox.session(python="3.12")
def benchmark(session: nox.Session) -> None:
    """Benchmark tests."""
    _install_dep_group(session, "build-system", "benchmark")
    project_install: tuple[str, ...] = ("-e", ".")
    posargs = session.posargs.copy()
    if "--wheel" in posargs:
        index = posargs.index("--wheel")
        posargs.pop(index)
        project_install = (posargs.pop(index),)
    env = {"CIBUILDWHEEL": "1"}
    update_env_macos(session, env)
    session.install("--no-deps", "--no-build-isolation", *project_install, env=env)
    session.run("pytest", "--codspeed", *posargs)


@nox.session(python="3.12")
def docs(session: nox.Session) -> None:
    """Build the docs."""
    _install_dep_group(session, "build-system", "docs")
    session.install("--no-deps", "--no-build-isolation", ".")
    session.chdir("docs")
    session.run(
        "python",
        "-m",
        "sphinx",
        "-T",
        "-E",
        "-b",
        "html",
        "-d",
        "_build/doctrees",
        "-D",
        "language=en",
        ".",
        "build",
    )


@nox.session(python="3.14", reuse_venv=True)
def sbom(session: nox.Session) -> None:
    """Embed SBOM file in wheels."""
    session.run("python", "tools/embed_sbom.py", *session.posargs)


@nox.session(python="3.12")
def update_requirements(session: nox.Session) -> None:
    pyproject = nox.project.load_toml()
    if session.venv_backend != "uv":
        uv_requirement = pyproject["tool"]["uv"]["required-version"]
        session.install(f"uv{uv_requirement}")
    session.run(
        "uv",
        "lock",
        "--no-build",
        "--upgrade",
    )
    for group in pyproject["dependency-groups"]:
        if group in {"dev", "nox"}:
            continue
        session.run(
            "uv",
            "export",
            "--format=requirements.txt",
            "--frozen",
            f"--only-group={group}",
            f"--output-file=requirements/{group}/requirements-ci.txt",
        )
