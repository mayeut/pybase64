from __future__ import annotations

__lazy_modules__ = ["pybase64._license"]

from pybase64._license import _license
from pybase64._version import _version

try:
    from pybase64._pybase64 import (
        _get_simd_path,
        _get_simd_paths_compile,  # noqa: F401
        _get_simd_paths_runtime,  # noqa: F401
        _set_simd_path,  # noqa: F401
        b64decode,
        b64decode_as_bytearray,
        b64encode,
        b64encode_as_string,
        encodebytes,
        standard_b64decode,
        standard_b64encode,
        urlsafe_b64decode,
        urlsafe_b64encode,
    )
except ImportError:
    from pybase64._fallback import (
        _get_simd_path,
        b64decode,
        b64decode_as_bytearray,
        b64encode,
        b64encode_as_string,
        encodebytes,
        standard_b64decode,
        standard_b64encode,
        urlsafe_b64decode,
        urlsafe_b64encode,
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
    simd_name = _get_simd_path()
    if simd_name != "py":
        return f"{__version__} (C extension active - {simd_name})"
    return f"{__version__} (C extension inactive)"
