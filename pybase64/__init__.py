from ._version import __version__

try:
    import _pybase64
    _has_extension = True
except ImportError:
    import base64
    _has_extension = False

import binascii
import sys

if sys.version_info < (3,0):
    bytes_types = (bytes, bytearray, str)  # Types acceptable as binary data
else:
    bytes_types = (bytes, bytearray)  # Types acceptable as binary data

def _bytes_from_decode_data(s):
    if (sys.version_info >= (3,0) and isinstance(s, str)):
        try:
            return s.encode('ascii')
        except UnicodeEncodeError:
            raise ValueError('string argument should contain only ASCII characters')
    if (sys.version_info < (3,0) and isinstance(s, unicode)):
        try:
            return s.encode('ascii')
        except UnicodeEncodeError:
            raise ValueError('string argument should contain only ASCII characters')
    if isinstance(s, bytes_types):
        return s
    try:
        return memoryview(s).tobytes()
    except TypeError:
        raise TypeError("argument should be a bytes-like object or ASCII "
                        "string, not %r" % s.__class__.__name__)

# Base64 encoding/decoding uses binascii

def b64encode(s, altchars=None):
    """Encode the bytes-like object s using Base64 and return a bytes object.
    Optional altchars should be a byte string of length 2 which specifies an
    alternative alphabet for the '+' and '/' characters.  This allows an
    application to e.g. generate url or filesystem safe Base64 strings.
    """
    if _has_extension:
        if altchars is not None:
            altchars = _bytes_from_decode_data(altchars)
            assert len(altchars) == 2, repr(altchars)
        return _pybase64.encode(s, altchars)
    else:
        return base64.b64encode(s, altchars)

def b64decode(s, altchars=None, validate=False):
    """Decode the Base64 encoded bytes-like object or ASCII string s.
    Optional altchars must be a bytes-like object or ASCII string of length 2
    which specifies the alternative alphabet used instead of the '+' and '/'
    characters.
    The result is returned as a bytes object.  A binascii.Error is raised if
    s is incorrectly padded.
    If validate is False (the default), characters that are neither in the
    normal base-64 alphabet nor the alternative alphabet are discarded prior
    to the padding check.  If validate is True, these non-alphabet characters
    in the input result in a binascii.Error.
    """
    if _has_extension:
        s = _bytes_from_decode_data(s)
        if altchars is not None:
            altchars = _bytes_from_decode_data(altchars)
            assert len(altchars) == 2, repr(altchars)
        try:
            decoded = _pybase64.decode(s, altchars, validate)
        except LookupError:
            raise binascii.Error('Non-base64 digit found')
        return decoded
    else:
        return base64.b64decode(s, altchars, validate)

def standard_b64encode(s):
    """Encode bytes-like object s using the standard Base64 alphabet.
    The result is returned as a bytes object.
    """
    return b64encode(s)

def standard_b64decode(s):
    """Decode bytes encoded with the standard Base64 alphabet.
    Argument s is a bytes-like object or ASCII string to decode.  The result
    is returned as a bytes object.  A binascii.Error is raised if the input
    is incorrectly padded.  Characters that are not in the standard alphabet
    are discarded prior to the padding check.
    """
    return b64decode(s)

def urlsafe_b64encode(s):
    """Encode bytes using the URL- and filesystem-safe Base64 alphabet.
    Argument s is a bytes-like object to encode.  The result is returned as a
    bytes object.  The alphabet uses '-' instead of '+' and '_' instead of
    '/'.
    """
    return b64encode(s, b'-_')

def urlsafe_b64decode(s):
    """Decode bytes using the URL- and filesystem-safe Base64 alphabet.
    Argument s is a bytes-like object or ASCII string to decode.  The result
    is returned as a bytes object.  A binascii.Error is raised if the input
    is incorrectly padded.  Characters that are not in the URL-safe base-64
    alphabet, and are not a plus '+' or slash '/', are discarded prior to the
    padding check.
    The alphabet uses '-' instead of '+' and '_' instead of '/'.
    """
    return b64decode(s, b'-_')

