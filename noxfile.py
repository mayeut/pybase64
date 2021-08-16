import nox


@nox.session
def lint(session: nox.Session) -> None:
    """
    Run linters on the codebase.
    """
    session.install("pre-commit")
    session.run("pre-commit", "run", "-a")
