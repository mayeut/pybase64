from __future__ import annotations

import sys
from base64 import b64decode as builtin_decode
from base64 import b64encode as builtin_encode
from base64 import encodebytes as builtin_encodebytes
from binascii import Error as BinAsciiError

from pybase64._unspecified import _Unspecified

TYPE_CHECKING = False
if TYPE_CHECKING:
    from typing import Final, Literal

    from pybase64._typing import Buffer


_SLOW_VALIDATION: Final = sys.version_info[:2] < (3, 13)  # fast/correct validation in CPython 3.13+
_PYTHON_3_15_API: Final = sys.hexversion >= 0x030F00A8  # in 3.15.0a8, move sys.version_info check
_BYTES_TYPES: Final = (bytes, bytearray)  # Types acceptable as binary data
_EQUAL_ASCII: Final = 61  # '='
_UNSPECIFIED: Final = _Unspecified.UNSPECIFIED

if not _PYTHON_3_15_API:
    # we consider '=' part of the alphabet, it will be handled separately
    _BASE64_ALPHABET = b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/="
    # we do not keep '=' on purpose, it will be handled separately
    _IGNORECHARS_VALIDATE_FALSE: Final = bytes(i for i in range(256) if i not in _BASE64_ALPHABET)


def _get_simd_name(flags: int) -> str:
    assert flags == 0  # noqa: S101
    return "fallback"


def _get_simd_path() -> int:
    return 0


def _get_bytes(s: str | Buffer, *, allow_str: bool = True) -> bytes | bytearray:
    if isinstance(s, str):
        if not allow_str:
            msg = "argument should be a bytes-like object "
            raise TypeError(msg) from None
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


def _validate_altchars(altchars: bytes | bytearray) -> bytes | bytearray | None:
    if len(altchars) != 2:
        msg = "len(altchars) != 2"
        raise ValueError(msg) from None
    if altchars == b"+/":
        return None
    return altchars


def b64decode(  # noqa: C901
    s: str | Buffer,
    altchars: str | Buffer | None = None,
    validate: bool | Literal[_Unspecified.UNSPECIFIED] = _UNSPECIFIED,
    *,
    ignorechars: Buffer | Literal[_Unspecified.UNSPECIFIED] = _UNSPECIFIED,
) -> bytes:
    """Decode bytes encoded with the standard Base64 alphabet.

    Argument ``s`` is a :term:`bytes-like object` or ASCII string to
    decode.

    Optional ``altchars`` must be a :term:`bytes-like object` or ASCII
    string of length 2 which specifies the alternative alphabet used instead
    of the '+' and '/' characters.

    If ``ignorechars`` is specified, it should be a :term:`bytes-like object`
    containing characters to ignore from the input when ``validate`` is ``True``.
    If ``ignorechars`` contains the pad character ``'='``,  the pad characters
    presented before the end of the encoded data and the excess pad characters
    will be ignored.
    The default value of ``validate`` is ``True`` if ``ignorechars`` is specified,
    ``False`` otherwise.

    If ``validate`` is ``False``, characters that are neither in
    the normal base-64 alphabet nor the alternative alphabet are discarded
    prior to the padding check.
    If ``validate`` is ``True``, these non-alphabet characters in the input
    result in a :exc:`binascii.Error`.

    The result is returned as a :class:`bytes` object.

    A :exc:`binascii.Error` is raised if ``s`` is incorrectly padded.
    """
    s = _get_bytes(s)
    has_bad_chars = False
    if altchars is not None:
        altchars = _validate_altchars(_get_bytes(altchars))

    if validate is _UNSPECIFIED:
        validate = ignorechars is not _UNSPECIFIED

    if ignorechars is not _UNSPECIFIED and not validate:
        msg = "validate must be True or unspecified when ignorechars is specified"
        raise ValueError(msg)

    if _PYTHON_3_15_API:
        kwargs: dict[str, bool | Buffer] = {"validate": validate}
        if ignorechars is not _UNSPECIFIED:
            kwargs["ignorechars"] = ignorechars
        return builtin_decode(s, altchars, **kwargs)  # type: ignore[arg-type]

    if ignorechars is not _UNSPECIFIED:
        ignorechars_ = _get_bytes(ignorechars, allow_str=False)

    if altchars is not None:
        if ignorechars is _UNSPECIFIED:
            for b in b"+/":
                if b not in altchars and b in s:
                    has_bad_chars = True
                    break
            trans = bytes.maketrans(altchars, b"+/")
            s = s.translate(trans)
        else:
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
            ignorechars_ = ignorechars_.translate(trans)

    if (not validate) or (ignorechars is not _UNSPECIFIED):
        # we need to filter s before calling builtin_decode this might be quite slow
        if not validate:
            has_equal = True
            ignorechars_ = _IGNORECHARS_VALIDATE_FALSE
        else:
            has_equal = 61 in ignorechars_
            ignorechars_ = bytes(set(ignorechars_) - set(_BASE64_ALPHABET))
        if ignorechars_:
            s = s.translate(None, delete=ignorechars_)
        if has_equal and s:
            if s[-1] != 61:  # there's data at the end, strip all padding bytes
                s = s.translate(None, delete=b"=")
            else:
                # get s without padding
                last_equal = len(s) - 1
                while (last_equal >= 0) and s[last_equal] == 61:
                    last_equal -= 1
                last_equal += 1
                equal_count = len(s) - last_equal
                s2 = s[:last_equal].translate(None, delete=b"=")
                quad_pos = len(s2) % 4
                if quad_pos in {0, 1} or (
                    quad_pos == 2 and equal_count == 1
                ):  # 0 is OK, 1 will fail
                    s = s2
                else:
                    s = s2 + b"=" * (4 - quad_pos)

    # we always do validation, start with a simple check
    if len(s) % 4 != 0:
        msg = "Incorrect padding"
        raise BinAsciiError(msg)

    if _SLOW_VALIDATION:
        result = builtin_decode(s, validate=False)

        # check length of result vs length of input
        expected_len = 0
        if s:
            padding = 0
            # len(s) % 4 != 0 implies len(s) >= 4 here
            if s[-2] == _EQUAL_ASCII:
                padding += 1
            if s[-1] == _EQUAL_ASCII:
                padding += 1
            expected_len = 3 * (len(s) // 4) - padding
        if expected_len != len(result):
            msg = "Non-base64 digit found"
            raise BinAsciiError(msg)
    else:
        result = builtin_decode(s, validate=True)
    if has_bad_chars:
        import warnings  # noqa: PLC0415 lazy import

        msg = f"invalid characters '+' or '/' in Base64 data with altchars={altchars!r}"
        if validate:
            msg = f"{msg} and validate=True will be an error in future versions"
            warnings.warn(msg, DeprecationWarning, stacklevel=2)
        else:
            msg = f"{msg} and validate=False will be discarded in future versions"
            warnings.warn(msg, FutureWarning, stacklevel=2)
    return result


def b64decode_as_bytearray(
    s: str | Buffer,
    altchars: str | Buffer | None = None,
    validate: bool | Literal[_Unspecified.UNSPECIFIED] = _UNSPECIFIED,
    *,
    ignorechars: Buffer | Literal[_Unspecified.UNSPECIFIED] = _UNSPECIFIED,
) -> bytearray:
    """Decode bytes encoded with the standard Base64 alphabet.

    Argument ``s`` is a :term:`bytes-like object` or ASCII string to
    decode.

    Optional ``altchars`` must be a :term:`bytes-like object` or ASCII
    string of length 2 which specifies the alternative alphabet used instead
    of the '+' and '/' characters.

    If ``ignorechars`` is specified, it should be a :term:`bytes-like object`
    containing characters to ignore from the input when ``validate`` is ``True``.
    If ``ignorechars`` contains the pad character ``'='``,  the pad characters
    presented before the end of the encoded data and the excess pad characters
    will be ignored.
    The default value of ``validate`` is ``True`` if ``ignorechars`` is specified,
    ``False`` otherwise.

    If ``validate`` is ``False``, characters that are neither in
    the normal base-64 alphabet nor the alternative alphabet are discarded
    prior to the padding check.
    If ``validate`` is ``True``, these non-alphabet characters in the input
    result in a :exc:`binascii.Error`.

    The result is returned as a :class:`bytearray` object.

    A :exc:`binascii.Error` is raised if ``s`` is incorrectly padded.
    """
    return bytearray(b64decode(s, altchars=altchars, validate=validate, ignorechars=ignorechars))


def b64encode(
    s: Buffer,
    altchars: str | Buffer | None = None,
    *,
    padded: bool = True,
    wrapcol: int = 0,
) -> bytes:
    r"""Encode bytes using the standard Base64 alphabet.

    Argument ``s`` is a :term:`bytes-like object` to encode.

    Optional ``altchars`` must be a byte string of length 2 which specifies
    an alternative alphabet for the '+' and '/' characters.  This allows an
    application to e.g. generate url or filesystem safe Base64 strings.

    Optional ``padded`` specifies whether to pad the encoded data with the '='
    character to a size multiple of 4.

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
        altchars = _validate_altchars(_get_bytes(altchars))
    if wrapcol < 0:
        msg = "wrapcol must be >= 0"
        raise ValueError(msg)
    if _PYTHON_3_15_API:  # pragma: no cover
        return builtin_encode(s, altchars, padded=padded, wrapcol=wrapcol)  # type: ignore[call-arg]
    encoded = builtin_encode(s, altchars)
    if encoded and not padded:
        # len is >= 4
        if encoded[-2] == _EQUAL_ASCII:
            encoded = encoded[:-2]
        elif encoded[-1] == _EQUAL_ASCII:
            encoded = encoded[:-1]
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
    padded: bool = True,
    wrapcol: int = 0,
) -> str:
    r"""Encode bytes using the standard Base64 alphabet.

    Argument ``s`` is a :term:`bytes-like object` to encode.

    Optional ``altchars`` must be a byte string of length 2 which specifies
    an alternative alphabet for the '+' and '/' characters.  This allows an
    application to e.g. generate url or filesystem safe Base64 strings.

    Optional ``padded`` specifies whether to pad the encoded data with the '='
    character to a size multiple of 4.

    Optional ``wrapcol`` specifies after how many characters the output should
    be split with a newline character (``'\n'``).  The value is rounded down
    to the nearest multiple of 4.  If ``wrapcol`` is 0 (the default), no
    newlines are added.

    The result is returned as a :class:`str` object.
    """
    return b64encode(s, altchars, padded=padded, wrapcol=wrapcol).decode("ascii")


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
