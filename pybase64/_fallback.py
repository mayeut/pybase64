from base64 import b64decode as builtin_decode
from base64 import b64encode as builtin_encode
from sys import version_info

from six import binary_type, text_type


__all__ = ['b64decode', 'b64encode']


if version_info < (3, 0):
    from binascii import Error as BinAsciiError
    from re import match as re_match
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
    if version_info < (3, 0):
        s = _get_bytes(s)
        if altchars is not None:
            altchars = _get_bytes(altchars)
            assert len(altchars) == 2, repr(altchars)
            s = s.translate(maketrans(altchars, b'+/'))
        if validate and not re_match(b'^[A-Za-z0-9+/]*={0,2}$', s):
            raise BinAsciiError('Non-base64 digit found')
        try:
            return builtin_decode(s, altchars)
        except TypeError as e:
            raise BinAsciiError(str(e))
    return builtin_decode(s, altchars, validate)


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
            raise TypeError('a bytes-like object is required, not \'' +
                            type(s).__name__ + '\'')
    return builtin_encode(s, altchars)
