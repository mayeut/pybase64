# coding: utf-8

from __future__ import unicode_literals

import base64
import unittest
from binascii import Error as BinAsciiError
from builtins import str

import pybase64


class TestPyBase64(unittest.TestCase):

    def setUp(self):
        pass

    def test_version(self):
        self.assertTrue(
            pybase64.get_version().startswith(pybase64.__version__)
        )

    def test_standard_b64encode(self):
        '''
        standard_b64encode shall give the same result as base64 built-in module
        '''
        self.assertEqual(
            pybase64.standard_b64encode(b'this is a test'),
            base64.standard_b64encode(b'this is a test')
        )

    def test_standard_roundtrip(self):
        '''
        Round trip shall return identity
        '''
        self.assertEqual(
            pybase64.standard_b64decode(
                pybase64.standard_b64encode(b'this is a test')
            ),
            b'this is a test'
        )
        self.assertEqual(
            pybase64.standard_b64encode(
                pybase64.standard_b64decode(
                    b'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdef'
                    b'ghijklmnopqrstuvwxyz0123456789+/'
                )
            ),
            b'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdef'
            b'ghijklmnopqrstuvwxyz0123456789+/'
        )

    def test_standard_roundtrip_unicode(self):
        '''
        Round trip shall return identity
        '''
        self.assertEqual(
            pybase64.standard_b64decode(
                str(pybase64.standard_b64encode(b'this is a test'), 'ascii')
            ),
            b'this is a test')
        for validate in [True, False]:
            self.assertEqual(
                pybase64.b64decode(
                    str(
                        pybase64.b64encode(b'this is a test', u'+/'),
                        'ascii'),
                    u'+/',
                    validate
                ),
                b'this is a test'
            )

    def test_urlsafe_b64encode(self):
        '''
        urlsafe_b64encode shall give the same result as base64 built-in module
        '''
        self.assertEqual(
            pybase64.urlsafe_b64encode(b'this is a test'),
            base64.urlsafe_b64encode(b'this is a test')
        )

    def test_urlsafe_roundtrip(self):
        '''
        Round trip shall return identity
        '''
        self.assertEqual(
            pybase64.urlsafe_b64decode(
                pybase64.urlsafe_b64encode(b'this is a test' * 10000)
            ),
            b'this is a test' * 10000
        )
        self.assertEqual(
            pybase64.urlsafe_b64encode(
                pybase64.urlsafe_b64decode(
                    b'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdef'
                    b'ghijklmnopqrstuvwxyz0123456789-_'
                )
            ),
            b'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdef'
            b'ghijklmnopqrstuvwxyz0123456789-_'
        )
        for validate in [True, False]:
            self.assertEqual(
                pybase64.b64decode(
                    pybase64.urlsafe_b64encode(b'this is a test' * 10000),
                    b'-_',
                    validate
                ),
                b'this is a test' * 10000
            )
            self.assertEqual(
                pybase64.urlsafe_b64encode(
                    pybase64.b64decode(
                        b'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdef'
                        b'ghijklmnopqrstuvwxyz0123456789-_',
                        b'-_',
                        validate
                    )
                ),
                b'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdef'
                b'ghijklmnopqrstuvwxyz0123456789-_'
            )
            self.assertEqual(
                pybase64.urlsafe_b64encode(
                    pybase64.b64decode(
                        b'_-_ABC_-_-_-_-_-_A-_',
                        b'-_',
                        validate
                    )
                ),
                b'_-_ABC_-_-_-_-_-_A-_'
            )
            self.assertEqual(
                pybase64.urlsafe_b64encode(
                    pybase64.b64decode(
                        b'_-_A',
                        b'-_',
                        validate
                    )
                ),
                b'_-_A'
            )

    def test_roundtrip(self):
        for validate in [True, False]:
            self.assertEqual(
                pybase64.b64decode(
                    str(
                        pybase64.b64encode(b'this is a test', u'+-'),
                        'ascii'),
                    u'+-',
                    validate=validate
                ),
                b'this is a test'
            )

    def test_b64encode_altchars_invalid(self):
        with self.assertRaises(AssertionError):
            pybase64.b64encode(b'this is a test', b'')
        with self.assertRaises(AssertionError):
            pybase64.b64encode(b'this is a test', b'-')
        with self.assertRaises(AssertionError):
            pybase64.b64encode(b'this is a test', b'-__')
        with self.assertRaises(TypeError):
            pybase64.b64encode(b'this is a test', 3.0)
        with self.assertRaises(ValueError):
            pybase64.b64encode(b'this is a test', '-€')

    def test_b64decode_altchars_invalid(self):
        for validate in [True, False]:
            with self.assertRaises(AssertionError):
                pybase64.b64decode(b'ABCD', b'', validate=validate)
            with self.assertRaises(AssertionError):
                pybase64.b64decode(b'ABCD', b'-', validate=validate)
            with self.assertRaises(AssertionError):
                pybase64.b64decode(b'ABCD', b'-__', validate=validate)
            with self.assertRaises(TypeError):
                pybase64.b64decode(b'ABCD', 3.0, validate=validate)
            with self.assertRaises(ValueError):
                pybase64.b64decode(b'this is a test', '-€', validate=validate)

    def test_b64decode_invalid_data(self):
        with self.assertRaises(BinAsciiError):
            pybase64.b64decode(b'\x00\x00\x00\x00', None, True)
        with self.assertRaises(BinAsciiError):
            pybase64.b64decode(
                b'A@@@@FGHIJKLMNOPQRSTUVWXYZabcdef',
                b'-_',
                True
            )
        with self.assertRaises(BinAsciiError):
            pybase64.b64decode(
                b'A@@@@FGH' * 10000,
                b'-_',
                True
            )
# TODO this does no fail under python3, add an option
#        with self.assertRaises(BinAsciiError):
#            pybase64.b64decode(
#                b'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdef'
#                b'ghijklmnopqrstuvwxyz0123456789+/',
#                b'-_',
#                True
#            )
        for validate in [True, False]:
            with self.assertRaises(BinAsciiError):
                pybase64.b64decode(
                    b'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdef'
                    b'ghijklmnopqrstuvwxyz0123456789-_',
                    validate=validate
                )
            with self.assertRaises(ValueError):
                pybase64.b64decode(u'ABC€', validate=validate)
            with self.assertRaises(TypeError):
                pybase64.b64decode(3.0, validate=validate)

    def test_b64encode_invalid_type(self):
        with self.assertRaises(TypeError):
            pybase64.b64encode(u'this is a test')

    def test_b64encode_invalid_args(self):
        with self.assertRaises(TypeError):
            pybase64.b64encode()

    def test_b64decode_invalid_args(self):
        with self.assertRaises(TypeError):
            pybase64.b64decode()

    def test_b64decode_novalidation(self):
        self.assertEqual(
            pybase64.b64decode(b'A@@@@FGH'),
            pybase64.b64decode(b'AFGH'))
