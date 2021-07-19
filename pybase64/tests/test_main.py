import os
import re
import sys

import pytest

import pybase64
from pybase64.__main__ import main


@pytest.fixture
def emptyfile(tmpdir):
    _file = os.path.join(tmpdir.strpath, "empty")
    with open(_file, "wb"):
        pass
    yield _file
    os.remove(_file)


@pytest.fixture
def hellofile(tmpdir):
    _file = os.path.join(tmpdir.strpath, "helloworld")
    with open(_file, "wb") as f:
        f.write(b"hello world !/?\n")
    yield _file
    os.remove(_file)


def idfn_test_help(args):
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
def test_help(capsys, args):
    if len(args) == 2:
        usage = f"usage: pybase64 {args[0]} [-h]"
    else:
        usage = "usage: pybase64 [-h]"
    with pytest.raises(SystemExit) as exit_info:
        main(args)
    captured = capsys.readouterr()
    assert captured.err == ""
    assert captured.out.startswith(usage)
    assert exit_info.value.code == 0


def test_version(capsys):
    with pytest.raises(SystemExit) as exit_info:
        main(["-V"])
    captured = capsys.readouterr()
    assert captured.err == ""
    assert captured.out.startswith("pybase64 " + pybase64.__version__)
    assert exit_info.value.code == 0


def test_license(capsys):
    restr = "\n".join(
        x + "\n[=]+\n.*Copyright.*\n[=]+\n" for x in ["pybase64", "libbase64"]
    )
    regex = re.compile("^" + restr + "$", re.DOTALL)
    with pytest.raises(SystemExit) as exit_info:
        main(["--license"])
    captured = capsys.readouterr()
    assert captured.err == ""
    assert regex.match(captured.out)
    assert exit_info.value.code == 0


def test_benchmark(capsys, emptyfile):
    main(["benchmark", "-d", "0.005", emptyfile])
    captured = capsys.readouterr()
    assert captured.err == ""
    assert captured.out != ""


@pytest.mark.parametrize(
    "args,expect",
    [
        ([], b"aGVsbG8gd29ybGQgIS8/Cg=="),
        (["-u"], b"aGVsbG8gd29ybGQgIS8_Cg=="),
        (["-a", ":,"], b"aGVsbG8gd29ybGQgIS8,Cg=="),
    ],
    ids=["0", "1", "2"],
)
def test_encode(capsysbinary, hellofile, args, expect):
    main(["encode"] + args + [hellofile])
    captured = capsysbinary.readouterr()
    assert captured.err == b""
    assert captured.out == expect


def test_encode_ouputfile(capsys, emptyfile, hellofile):
    main(["encode", "-o", hellofile, emptyfile])
    captured = capsys.readouterr()
    assert captured.err == ""
    assert captured.out == ""
    with open(hellofile, "rb") as f:
        data = f.read()
    assert data == b""


@pytest.mark.parametrize(
    "args,b64string",
    [
        [[], b"aGVsbG8gd29ybGQgIS8/Cg=="],
        [["-u"], b"aGVsbG8gd29ybGQgIS8_Cg=="],
        [["-a", ":,"], b"aGVsbG8gd29ybGQgIS8,Cg=="],
        [["--no-validation"], b"aGVsbG8gd29yb GQgIS8/Cg==\n"],
    ],
    ids=["0", "1", "2", "3"],
)
def test_decode(capsysbinary, tmpdir, args, b64string):
    iname = os.path.join(tmpdir.strpath, "in")
    with open(iname, "wb") as f:
        f.write(b64string)
    main(["decode"] + args + [iname])
    captured = capsysbinary.readouterr()
    assert captured.err == b""
    assert captured.out == b"hello world !/?\n"


def test_subprocess():
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
