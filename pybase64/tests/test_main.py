# coding: utf-8

import os
import re
import shutil
import sys
import tempfile
import unittest
from contextlib import contextmanager
from sys import version_info

import pybase64
from parameterized import parameterized
from pybase64.__main__ import main


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


class TestMain(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.tmppath = tempfile.mkdtemp()
        cls.emptyfile = os.path.join(cls.tmppath, 'empty')
        cls.hello = os.path.join(cls.tmppath, 'helloworld')
        with open(cls.emptyfile, 'wb'):
            pass
        with open(cls.hello, 'wb') as f:
            f.write(b'hello world !/?\n')

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmppath)

    @parameterized.expand([
        [[]],
        [['-h']],
        [['benchmark', '-h']],
        [['encode', '-h']],
        [['decode', '-h']],
    ])
    def test_help(self, args):
        if len(args) == 2:
            usage = 'usage: pybase64 {0} [-h]'.format(args[0])
        else:
            usage = 'usage: pybase64 [-h]'
        with capture(args) as c:
            self.assertEqual(c.err, '')
            self.assertTrue(c.out.startswith(usage))
            self.assertEqual(c.exception.code, 0)

    def test_version(self):
        with capture(['-V']) as c:
            if version_info < (3, 4):
                self.assertEqual(c.out, '')
                self.assertTrue(
                    c.err.startswith('pybase64 ' + pybase64.__version__))
            else:
                self.assertEqual(c.err, '')
                self.assertTrue(
                    c.out.startswith('pybase64 ' + pybase64.__version__))
            self.assertEqual(c.exception.code, 0)

    def test_license(self):
        restr = '\n'.join(x + '\n[=]+\n.*Copyright.*\n[=]+\n'
                          for x in ['pybase64', 'libbase64'])
        regex = re.compile('^' + restr + '$', re.DOTALL)
        with capture(['--license']) as c:
            self.assertEqual(c.err, '')
            if version_info < (3, 3):
                self.assertRegexpMatches(c.out, regex)  # deprecated
            else:
                self.assertRegex(c.out, regex)
            self.assertEqual(c.exception.code, 0)

    def test_benchmark(self):
        with capture(['benchmark', '-d', '0.005', self.emptyfile]) as c:
            self.assertEqual(c.exception, None)
            self.assertNotEqual(c.out, '')
            self.assertEqual(c.err, '')

    @parameterized.expand([
        [[], b'aGVsbG8gd29ybGQgIS8/Cg=='],
        [['-u'], b'aGVsbG8gd29ybGQgIS8_Cg=='],
        [['-a', ':,'], b'aGVsbG8gd29ybGQgIS8,Cg=='],
    ])
    def test_encode(self, args, expect):
        with capture(['encode'] + args + [self.hello],
                     newout=BytesIOBuffered()) as c:
            self.assertEqual(c.exception, None)
            self.assertEqual(c.out, expect)
            self.assertEqual(c.err, '')

    @parameterized.expand([
        [[], b'aGVsbG8gd29ybGQgIS8/Cg=='],
        [['-u'], b'aGVsbG8gd29ybGQgIS8_Cg=='],
        [['-a', ':,'], b'aGVsbG8gd29ybGQgIS8,Cg=='],
        [['--no-validation'], b'aGVsbG8gd29yb GQgIS8/Cg==\n'],
    ])
    def test_decode(self, args, b64string):
        iname = os.path.join(self.tmppath, 'in')
        with open(iname, 'wb') as f:
            f.write(b64string)
        with capture(['decode'] + args + [iname],
                     newout=BytesIOBuffered()) as c:
            self.assertEqual(c.exception, None)
            self.assertEqual(c.out, b'hello world !/?\n')
            self.assertEqual(c.err, '')

    def test_subprocess(self):
        import subprocess
        process = subprocess.Popen(
            [sys.executable, '-m', 'pybase64', 'encode', '-'],
            bufsize=4096,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)
        out, err = process.communicate()
        process.wait()
        self.assertEqual(process.returncode, 0)
        self.assertEqual(out, b'')
        self.assertEqual(err, b'')
