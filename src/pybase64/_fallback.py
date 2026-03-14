from __future__ import annotations

import sys
from base64 import b64decode as builtin_decode
from base64 import b64encode as builtin_encode
from base64 import encodebytes as builtin_encodebytes
from binascii import Error as BinAsciiError
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Final

    from ._typing import Buffer

_SLOW_VALIDATION: Final = sys.version_info[:2] < (3, 11)  # fast validation with CPython 3.11+
_HAS_WRAPCOL: Final = sys.version_info[:2] >= (3, 15)  # wrapcol support in builtin b64encode
_BYTES_TYPES: Final = (bytes, bytearray)  # Types acceptable as binary data


def _get_simd_name(flags: int) -> str:
    assert flags == 0  # noqa: S101
    return "fallback"


def _get_simd_path() -> int:
    return 0


def _get_bytes(s: str | Buffer) -> bytes | bytearray:
    if isinstance(s, str):
        try:
            return s.encode("ascii")
        except UnicodeEncodeError:
            msg = "string argument should contain only ASCII characters"
            raise ValueError(msg) from None
    if isinstance(s, _BYTES_TYPES):
        return s
    try:
        mv = memoryview(s)
        if not mv.c_contiguous:
            msg = f"{s.__class__.__name__!r:s}: underlying buffer is not C-contiguous"
            raise BufferError(msg)
        return mv.tobytes()
    except TypeError:
        msg = (
            "argument should be a bytes-like object or ASCII "
            f"string, not {s.__class__.__name__!r:s}"
        )
        raise TypeError(msg) from None


def _validate_altchars(altchars: bytes | bytearray) -> None:
    if len(altchars) != 2:
        msg = "len(altchars) != 2"
        raise ValueError(msg) from None


def b64decode(
    s: str | Buffer,
    altchars: str | Buffer | None = None,
    validate: bool = False,
) -> bytes:
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
    s = _get_bytes(s)
    if altchars is not None:
        altchars = _get_bytes(altchars)
        if altchars != b"+/":
            _validate_altchars(altchars)
            trans_in_add = set(b"+/") - set(altchars)
            if len(trans_in_add) == 2:
                # we don't want to use an unordered set for 2 elements
                trans = bytes.maketrans(altchars + b"+/", b"+/" + altchars)
            else:
                # 0 or 1 element in the set
                trans = bytes.maketrans(
                    altchars + bytes(trans_in_add),
                    b"+/" + bytes(set(altchars) - set(b"+/")),
                )
            s = s.translate(trans)

    if _SLOW_VALIDATION and validate:
        if len(s) % 4 != 0:
            msg = "Incorrect padding"
            raise BinAsciiError(msg)
        result = builtin_decode(s, validate=False)

        # check length of result vs length of input
        expected_len = 0
        if len(s) > 0:
            padding = 0
            # len(s) % 4 != 0 implies len(s) >= 4 here
            if s[-2] == 61:  # 61 == ord("=")
                padding += 1
            if s[-1] == 61:
                padding += 1
            expected_len = 3 * (len(s) // 4) - padding
        if expected_len != len(result):
            msg = "Non-base64 digit found"
            raise BinAsciiError(msg)
    else:
        result = builtin_decode(s, validate=validate)
    return result


def b64decode_as_bytearray(
    s: str | Buffer,
    altchars: str | Buffer | None = None,
    validate: bool = False,
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


def b64encode(s: Buffer, altchars: str | Buffer | None = None, *, wrapcol: int = 0) -> bytes:
    r"""Encode bytes using the standard Base64 alphabet.

    Argument ``s`` is a :term:`bytes-like object` to encode.

    Optional ``altchars`` must be a byte string of length 2 which specifies
    an alternative alphabet for the '+' and '/' characters.  This allows an
    application to e.g. generate url or filesystem safe Base64 strings.

    Optional ``wrapcol`` specifies after how many characters the output should
    be split with a newline character (``b'\n'``).  The value is rounded down
    to the nearest multiple of 4.  If ``wrapcol`` is 0 (the default), no
    newlines are added.

    The result is returned as a :class:`bytes` object.
    """
    mv = memoryview(s)
    if not mv.c_contiguous:
        msg = f"{s.__class__.__name__!r:s}: underlying buffer is not C-contiguous"
        raise BufferError(msg)
    if altchars is not None:
        altchars = _get_bytes(altchars)
        _validate_altchars(altchars)
    if wrapcol < 0:
        msg = "wrapcol must be >= 0"
        raise ValueError(msg)
    if _HAS_WRAPCOL:
        return builtin_encode(s, altchars, wrapcol=wrapcol)  # type: ignore[call-arg]
    encoded = builtin_encode(s, altchars)
    if wrapcol == 0 or not encoded:
        return encoded
    effective_wrapcol = (wrapcol // 4) * 4 or 4
    return b"\n".join(
        encoded[i : i + effective_wrapcol] for i in range(0, len(encoded), effective_wrapcol)
    )


def b64encode_as_string(
    s: Buffer,
    altchars: str | Buffer | None = None,
    *,
    wrapcol: int = 0,
) -> str:
    r"""Encode bytes using the standard Base64 alphabet.

    Argument ``s`` is a :term:`bytes-like object` to encode.

    Optional ``altchars`` must be a byte string of length 2 which specifies
    an alternative alphabet for the '+' and '/' characters.  This allows an
    application to e.g. generate url or filesystem safe Base64 strings.

    Optional ``wrapcol`` specifies after how many characters the output should
    be split with a newline character (``'\n'``).  The value is rounded down
    to the nearest multiple of 4.  If ``wrapcol`` is 0 (the default), no
    newlines are added.

    The result is returned as a :class:`str` object.
    """
    return b64encode(s, altchars, wrapcol=wrapcol).decode("ascii")


def encodebytes(s: Buffer) -> bytes:
    r"""Encode bytes into a bytes object with newlines (b'\n') inserted after
    every 76 bytes of output, and ensuring that there is a trailing newline,
    as per :rfc:`2045` (MIME).

    Argument ``s`` is a :term:`bytes-like object` to encode.

    The result is returned as a :class:`bytes` object.
    """  # noqa: D205
    mv = memoryview(s)
    if not mv.c_contiguous:
        msg = f"{s.__class__.__name__!r:s}: underlying buffer is not C-contiguous"
        raise BufferError(msg)
    return builtin_encodebytes(s)
