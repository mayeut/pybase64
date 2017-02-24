import unittest
import pybase64
import base64

class TestPyBase64(unittest.TestCase):

    def setUp(self):
        pass

    def test_standard_b64encode(self):
        '''
        standard_b64encode shall give the same result as base64 built-in module
        '''
        self.assertEqual(
                pybase64.standard_b64encode(b'this is a test'),
                  base64.standard_b64encode(b'this is a test'))

    def test_standard_roundtrip(self):
        '''
        Round trip shall return identity
        '''
        self.assertEqual(
                pybase64.standard_b64decode(pybase64.standard_b64encode(b'this is a test')),
                  b'this is a test')

if __name__ == '__main__':
    unittest.main()
