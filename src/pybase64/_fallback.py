from base64 import b64decode as builtin_decode
from base64 import b64encode as builtin_encode
from base64 import encodebytes as builtin_encodebytes
from binascii import Error as BinAsciiError
from typing import Any, Union

__all__ = [
    "_get_simd_name",
    "_get_simd_path",
    "b64decode",
    "b64encode",
    "b64encode_as_string",
    "encodebytes",
]


_bytes_types = (bytes, bytearray)  # Types acceptable as binary data


def _get_simd_name(flags: int) -> str:
    assert flags == 0
    return "fallback"


def _get_simd_path() -> int:
    return 0


def _get_bytes(s: Any) -> Union[bytes, bytearray]:
    if isinstance(s, str):
        try:
            return s.encode("ascii")
        except UnicodeEncodeError:
            raise ValueError("string argument should contain only ASCII " "characters")
    if isinstance(s, _bytes_types):
        return s
    try:
        return memoryview(s).tobytes()
    except TypeError:
        raise TypeError(
            "argument should be a bytes-like object or ASCII "
            "string, not %r" % s.__class__.__name__
        )


def b64decode(s: Any, altchars: Any = None, validate: bool = False) -> bytes:
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
    if validate:
        if len(s) % 4 != 0:
            raise BinAsciiError("Incorrect padding")
        s = _get_bytes(s)
        if altchars is not None:
            altchars = _get_bytes(altchars)
            assert len(altchars) == 2, repr(altchars)
            map = bytes.maketrans(altchars, b"+/")
            s = s.translate(map)
        result = builtin_decode(s, altchars, validate=False)

        # check length of result vs length of input
        padding = 0
        if len(s) > 1 and s[-2] in (b"=", 61):
            padding = padding + 1
        if len(s) > 0 and s[-1] in (b"=", 61):
            padding = padding + 1
        if 3 * (len(s) / 4) - padding != len(result):
            raise BinAsciiError("Non-base64 digit found")
        return result
    return builtin_decode(s, altchars, validate=False)


def b64decode_as_bytearray(
    s: Any, altchars: Any = None, validate: bool = False
) -> bytearray:
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

    The result is returned as a :class:`bytearray` object.

    A :exc:`binascii.Error` is raised if ``s`` is incorrectly padded.
    """
    return bytearray(b64decode(s, altchars=altchars, validate=validate))


def b64encode(s: Any, altchars: Any = None) -> bytes:
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
    return builtin_encode(s, altchars)


def b64encode_as_string(s: Any, altchars: Any = None) -> str:
    """Encode bytes using the standard Base64 alphabet.

    Argument ``s`` is a :term:`bytes-like object` to encode.

    Optional ``altchars`` must be a byte string of length 2 which specifies
    an alternative alphabet for the '+' and '/' characters.  This allows an
    application to e.g. generate url or filesystem safe Base64 strings.

    The result is returned as a :class:`str` object.
    """
    return b64encode(s, altchars).decode("ascii")


def encodebytes(s: Any) -> bytes:
    """Encode bytes into a bytes object with newlines (b'\\\\n') inserted after
    every 76 bytes of output, and ensuring that there is a trailing newline,
    as per :rfc:`2045` (MIME).

    Argument ``s`` is a :term:`bytes-like object` to encode.

    The result is returned as a :class:`bytes` object.
    """
    return builtin_encodebytes(s)
