from base64 import b64decode as builtin_decode
from base64 import b64encode as builtin_encode
from binascii import Error as BinAsciiError
from sys import version_info

from six import binary_type, text_type


try:
    from base64 import encodebytes as builtin_encodebytes
except ImportError:
    from base64 import encodestring as builtin_encodebytes


__all__ = ['b64decode', 'b64encode', 'encodebytes']


if version_info < (3, 0):
    from string import maketrans

_bytes_types = (binary_type, bytearray)  # Types acceptable as binary data


def _get_bytes(s):
    if isinstance(s, text_type):
        try:
            return s.encode('ascii')
        except UnicodeEncodeError:
            raise ValueError('string argument should contain only ASCII '
                             'characters')
    if isinstance(s, _bytes_types):
        return s
    try:
        return memoryview(s).tobytes()
    except TypeError:
        raise TypeError('argument should be a bytes-like object or ASCII '
                        'string, not %r' % s.__class__.__name__)


def b64decode(s, altchars=None, validate=False):
    """Decode bytes encoded with the standard Base64 alphabet.

    Argument ``s`` is a :term:`bytes-like object` or ASCII string to
    decode.

    Optional ``altchars`` must be a :term:`bytes-like object` or ASCII
    string of length 2 which specifies the alternative alphabet used instead
    of the '+' and '/' characters.

    If ``validate`` is ``False`` (the default), characters that are neither in
    the normal base-64 alphabet nor the alternative alphabet are discarded
    prior to the padding check.
    If ``validate`` is ``True``, these non-alphabet characters in the input
    result in a :exc:`binascii.Error`.

    The result is returned as a :class:`bytes` object.

    A :exc:`binascii.Error` is raised if ``s`` is incorrectly padded.
    """
    if version_info < (3, 0) or validate:
        if validate and len(s) % 4 != 0:
            raise BinAsciiError('Incorrect padding')
        s = _get_bytes(s)
        if altchars is not None:
            altchars = _get_bytes(altchars)
            assert len(altchars) == 2, repr(altchars)
            if version_info < (3, 0):
                map = maketrans(altchars, b'+/')
            else:
                map = bytes.maketrans(altchars, b'+/')
            s = s.translate(map)
        try:
            result = builtin_decode(s, altchars)
        except TypeError as e:
            raise BinAsciiError(str(e))
        if validate:
            # check length of result vs length of input
            padding = 0
            if len(s) > 1 and s[-2] in (b'=', 61):
                padding = padding + 1
            if len(s) > 0 and s[-1] in (b'=', 61):
                padding = padding + 1
            if 3 * (len(s) / 4) - padding != len(result):
                raise BinAsciiError('Non-base64 digit found')
        return result
    return builtin_decode(s, altchars)


def b64encode(s, altchars=None):
    """Encode bytes using the standard Base64 alphabet.

    Argument ``s`` is a :term:`bytes-like object` to encode.

    Optional ``altchars`` must be a byte string of length 2 which specifies
    an alternative alphabet for the '+' and '/' characters.  This allows an
    application to e.g. generate url or filesystem safe Base64 strings.

    The result is returned as a :class:`bytes` object.
    """
    if altchars is not None:
        altchars = _get_bytes(altchars)
        assert len(altchars) == 2, repr(altchars)
    if version_info < (3, 0):
        if isinstance(s, text_type):
            raise TypeError('a bytes-like object is required, not \''
                            + type(s).__name__ + '\'')
    return builtin_encode(s, altchars)


def encodebytes(s):
    """Encode bytes into a bytes object with newlines (b'\n') inserted after
every 76 bytes of output, and ensuring that there is a trailing newline,
as per :rfc:`2045` (MIME).

Argument ``s`` is a :term:`bytes-like object` to encode.

The result is returned as a :class:`bytes` object.
    """
    return builtin_encodebytes(s)
