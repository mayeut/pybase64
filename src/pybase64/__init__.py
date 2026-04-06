from __future__ import annotations

__lazy_modules__ = ["pybase64._license"]

from pybase64._license import _license
from pybase64._version import _version

TYPE_CHECKING = False
if TYPE_CHECKING:
    from pybase64._typing import Buffer

try:
    from pybase64._pybase64 import (
        _get_simd_flags_compile,  # noqa: F401
        _get_simd_flags_runtime,  # noqa: F401
        _get_simd_name,
        _get_simd_path,
        _set_simd_path,  # noqa: F401
        b64decode,
        b64decode_as_bytearray,
        b64encode,
        b64encode_as_string,
        encodebytes,
    )
except ImportError:
    from pybase64._fallback import (
        _get_simd_name,
        _get_simd_path,
        b64decode,
        b64decode_as_bytearray,
        b64encode,
        b64encode_as_string,
        encodebytes,
    )


__all__ = (
    "b64decode",
    "b64decode_as_bytearray",
    "b64encode",
    "b64encode_as_string",
    "encodebytes",
    "standard_b64decode",
    "standard_b64encode",
    "urlsafe_b64decode",
    "urlsafe_b64encode",
)

__version__ = _version


def get_license_text() -> str:
    """Return pybase64 license information as a :class:`str` object.

    The result includes libbase64 license information as well.
    """
    return _license


def get_version() -> str:
    """Return pybase64 version as a :class:`str` object.

    The result reports if the C extension is used or not.
    e.g. `1.0.0 (C extension active - AVX2)`
    """
    simd_name = _get_simd_name(_get_simd_path())
    if simd_name != "fallback":
        return f"{__version__} (C extension active - {simd_name})"
    return f"{__version__} (C extension inactive)"


def standard_b64encode(s: Buffer) -> bytes:
    """Encode bytes using the standard Base64 alphabet.

    Argument ``s`` is a :term:`bytes-like object` to encode.

    The result is returned as a :class:`bytes` object.
    """
    return b64encode(s)


def standard_b64decode(s: str | Buffer) -> bytes:
    """Decode bytes encoded with the standard Base64 alphabet.

    Argument ``s`` is a :term:`bytes-like object` or ASCII string to
    decode.

    The result is returned as a :class:`bytes` object.

    A :exc:`binascii.Error` is raised if the input is incorrectly padded.

    Characters that are not in the standard alphabet are discarded prior
    to the padding check.
    """
    return b64decode(s)


def urlsafe_b64encode(s: Buffer, *, padded: bool = True) -> bytes:
    """Encode bytes using the URL- and filesystem-safe Base64 alphabet.

    Argument ``s`` is a :term:`bytes-like object` to encode.

    The result is returned as a :class:`bytes` object.

    The alphabet uses '-' instead of '+' and '_' instead of '/'.

    The result can still contain ``=`` if ``padded`` is true (default).
    """
    return b64encode(s, b"-_", padded=padded)


def urlsafe_b64decode(s: str | Buffer) -> bytes:
    """Decode bytes using the URL- and filesystem-safe Base64 alphabet.

    Argument ``s`` is a :term:`bytes-like object` or ASCII string to
    decode.

    The result is returned as a :class:`bytes` object.

    A :exc:`binascii.Error` is raised if the input is incorrectly padded.

    Characters that are not in the URL-safe base-64 alphabet, and are not
    a plus '+' or slash '/', are discarded prior to the padding check.

    The alphabet uses '-' instead of '+' and '_' instead of '/'.
    """
    return b64decode(s, b"-_")
