# coding: utf-8

import os
import re
import sys
from contextlib import contextmanager
from sys import version_info

import pybase64
from pybase64.__main__ import main

import pytest


try:
    from StringIO import StringIO
    from StringIO import StringIO as BytesIO
except ImportError:
    from io import StringIO
    from io import BytesIO


class CaptureObject:
    def __init__(self, out, err, exception):
        self.out = out
        self.err = err
        self.exception = exception


class StringIOBuffered(StringIO):
    def __init__(self):
        self._data = None
        StringIO.__init__(self)

    def data(self):
        self.close()
        return self._data

    def close(self):
        try:
            if self._data is None:
                self.seek(0)
                self._data = self.read()
        finally:
            StringIO.close(self)


class BytesIOBuffered(BytesIO):
    def __init__(self):
        self._data = None
        BytesIO.__init__(self)

    def data(self):
        self.close()
        return self._data

    def close(self):
        try:
            if self._data is None:
                self.seek(0)
                self._data = self.read()
        finally:
            BytesIO.close(self)


@contextmanager
def ioscope(file):
    try:
        yield file
    finally:
        file.close()


@contextmanager
def capture(args, newout=None):
    if newout is None:
        newout = StringIOBuffered()
    with ioscope(newout):
        with ioscope(StringIOBuffered()) as newerr:
            err, sys.stderr = sys.stderr, newerr
            out, sys.stdout = sys.stdout, newout
            try:
                try:
                    e = None
                    main(args)
                except BaseException as exception:
                    e = exception
                yield CaptureObject(sys.stdout.data(), sys.stderr.data(), e)
            finally:
                sys.stderr = err
                sys.stdout = out


@pytest.fixture
def emptyfile(tmpdir):
    _file = os.path.join(tmpdir.strpath, 'empty')
    with open(_file, 'wb'):
        pass
    yield _file
    os.remove(_file)


@pytest.fixture
def hellofile(tmpdir):
    _file = os.path.join(tmpdir.strpath, 'helloworld')
    with open(_file, 'wb') as f:
        f.write(b'hello world !/?\n')
    yield _file
    os.remove(_file)


def idfn_test_help(args):
    if len(args) == 0:
        return '(empty)'
    return ' '.join(args)


@pytest.mark.parametrize(
    "args",
    [
        [],
        ['-h'],
        ['benchmark', '-h'],
        ['encode', '-h'],
        ['decode', '-h'],
    ],
    ids=idfn_test_help
)
def test_help(args):
    if len(args) == 2:
        usage = 'usage: pybase64 {0} [-h]'.format(args[0])
    else:
        usage = 'usage: pybase64 [-h]'
    with capture(args) as c:
        assert c.err == ''
        assert c.out.startswith(usage)
        assert c.exception.code == 0


def test_version():
    with capture(['-V']) as c:
        if version_info < (3, 4):
            assert c.out == ''
            assert c.err.startswith('pybase64 ' + pybase64.__version__)
        else:
            assert c.err == ''
            assert c.out.startswith('pybase64 ' + pybase64.__version__)
        assert c.exception.code == 0


def test_license():
    restr = '\n'.join(x + '\n[=]+\n.*Copyright.*\n[=]+\n'
                      for x in ['pybase64', 'libbase64'])
    regex = re.compile('^' + restr + '$', re.DOTALL)
    with capture(['--license']) as c:
        assert c.err == ''
        assert regex.match(c.out)
        assert c.exception.code == 0


def test_benchmark(emptyfile):
    with capture(['benchmark', '-d', '0.005', emptyfile]) as c:
        assert c.exception is None
        assert c.out != ''
        assert c.err == ''


@pytest.mark.parametrize(
    "args,expect",
    [
        ([], b'aGVsbG8gd29ybGQgIS8/Cg=='),
        (['-u'], b'aGVsbG8gd29ybGQgIS8_Cg=='),
        (['-a', ':,'], b'aGVsbG8gd29ybGQgIS8,Cg=='),
    ],
    ids=['0', '1', '2']
)
def test_encode(hellofile, args, expect):
    with capture(['encode'] + args + [hellofile],
                 newout=BytesIOBuffered()) as c:
        assert c.exception is None
        assert c.out == expect
        assert c.err == ''


@pytest.mark.parametrize(
    "args,b64string",
    [
        [[], b'aGVsbG8gd29ybGQgIS8/Cg=='],
        [['-u'], b'aGVsbG8gd29ybGQgIS8_Cg=='],
        [['-a', ':,'], b'aGVsbG8gd29ybGQgIS8,Cg=='],
        [['--no-validation'], b'aGVsbG8gd29yb GQgIS8/Cg==\n'],
    ],
    ids=['0', '1', '2', '3']
)
def test_decode(tmpdir, args, b64string):
    iname = os.path.join(tmpdir.strpath, 'in')
    with open(iname, 'wb') as f:
        f.write(b64string)
    with capture(['decode'] + args + [iname],
                 newout=BytesIOBuffered()) as c:
        assert c.exception is None
        assert c.out == b'hello world !/?\n'
        assert c.err == ''


def test_subprocess():
    import subprocess
    process = subprocess.Popen(
        [sys.executable, '-m', 'pybase64', 'encode', '-'],
        bufsize=4096,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE)
    out, err = process.communicate()
    process.wait()
    assert process.returncode == 0
    assert out == b''
    assert err == b''
