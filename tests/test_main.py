from __future__ import annotations

import re
import sys
from collections.abc import Iterator, Sequence
from pathlib import Path

import pytest

import pybase64
from pybase64.__main__ import main


@pytest.fixture
def emptyfile(tmp_path: Path) -> Iterator[str]:
    _file = tmp_path / "empty"
    _file.write_bytes(b"")
    yield str(_file)
    _file.unlink()


@pytest.fixture
def hellofile(tmp_path: Path) -> Iterator[str]:
    _file = tmp_path / "helloworld"
    _file.write_bytes(b"hello world !/?\n")
    yield str(_file)
    _file.unlink()


def idfn_test_help(args: Sequence[str]) -> str:
    if len(args) == 0:
        return "(empty)"
    return " ".join(args)


@pytest.mark.parametrize(
    "args",
    [
        [],
        ["-h"],
        ["benchmark", "-h"],
        ["encode", "-h"],
        ["decode", "-h"],
    ],
    ids=idfn_test_help,
)
def test_help(capsys: pytest.CaptureFixture[str], args: Sequence[str]) -> None:
    command = "pybase64"
    if len(args) == 2:
        command += f" {args[0]}"
    usage = f"usage: {command} [-h]"
    with pytest.raises(SystemExit) as exit_info:
        main(args)
    captured = capsys.readouterr()
    assert captured.err == ""
    assert captured.out.startswith(usage)
    assert exit_info.value.code == 0


def test_version(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exit_info:
        main(["-V"])
    captured = capsys.readouterr()
    assert captured.err == ""
    assert captured.out.startswith("pybase64 " + pybase64.__version__)
    assert exit_info.value.code == 0


def test_license(capsys: pytest.CaptureFixture[str]) -> None:
    restr = "\n".join(x + "\n[=]+\n.*Copyright.*\n[=]+\n" for x in ["pybase64", "libbase64"])
    regex = re.compile("^" + restr + "$", re.DOTALL)
    with pytest.raises(SystemExit) as exit_info:
        main(["--license"])
    captured = capsys.readouterr()
    assert captured.err == ""
    assert regex.match(captured.out)
    assert exit_info.value.code == 0


def test_benchmark(capsys: pytest.CaptureFixture[str], emptyfile: str) -> None:
    main(["benchmark", "-d", "0.005", emptyfile])
    captured = capsys.readouterr()
    assert captured.err == ""
    assert captured.out != ""


@pytest.mark.parametrize(
    ("args", "expect"),
    [
        ([], b"aGVsbG8gd29ybGQgIS8/Cg=="),
        (["-u"], b"aGVsbG8gd29ybGQgIS8_Cg=="),
        (["-a", ":,"], b"aGVsbG8gd29ybGQgIS8,Cg=="),
    ],
    ids=["0", "1", "2"],
)
def test_encode(
    capsysbinary: pytest.CaptureFixture[bytes], hellofile: str, args: Sequence[str], expect: bytes
) -> None:
    main(["encode", *args, hellofile])
    captured = capsysbinary.readouterr()
    assert captured.err == b""
    assert captured.out == expect


def test_encode_ouputfile(
    capsys: pytest.CaptureFixture[str], emptyfile: str, hellofile: str
) -> None:
    main(["encode", "-o", hellofile, emptyfile])
    captured = capsys.readouterr()
    assert captured.err == ""
    assert captured.out == ""
    with open(hellofile, "rb") as f:
        data = f.read()
    assert data == b""


@pytest.mark.parametrize(
    ("args", "b64string"),
    [
        ([], b"aGVsbG8gd29ybGQgIS8/Cg=="),
        (["-u"], b"aGVsbG8gd29ybGQgIS8_Cg=="),
        (["-a", ":,"], b"aGVsbG8gd29ybGQgIS8,Cg=="),
        (["--no-validation"], b"aGVsbG8gd29yb GQgIS8/Cg==\n"),
    ],
    ids=["0", "1", "2", "3"],
)
def test_decode(
    capsysbinary: pytest.CaptureFixture[bytes],
    tmp_path: Path,
    args: Sequence[str],
    b64string: bytes,
) -> None:
    input_file = tmp_path / "in"
    input_file.write_bytes(b64string)
    main(["decode", *args, str(input_file)])
    captured = capsysbinary.readouterr()
    assert captured.err == b""
    assert captured.out == b"hello world !/?\n"


def test_subprocess() -> None:
    import subprocess

    process = subprocess.Popen(
        [sys.executable, "-m", "pybase64", "encode", "-"],
        bufsize=4096,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    out, err = process.communicate()
    process.wait()
    assert process.returncode == 0
    assert out == b""
    assert err == b""
