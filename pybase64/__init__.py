from ._version import __version__

try:
    __PYBASE64_SETUP__
except NameError:
    __PYBASE64_SETUP__ = False

# Only go on if not in setup.py
if not __PYBASE64_SETUP__:
    from ._license import _license
    try:
        from ._pybase64 import b64encode
        from ._pybase64 import b64decode
        from ._pybase64 import encodebytes  # noqa: F401
        from ._pybase64 import _get_simd_path
        _has_extension = True
    except ImportError:
        from ._fallback import b64encode
        from ._fallback import b64decode
        from ._fallback import encodebytes  # noqa: F401
        _has_extension = False

    def get_license_text():
        """Returns pybase64 license information as a :class:`str` object.

        The result includes libbase64 license information as well.
        """
        return _license

    def get_version():
        """Returns pybase64 version as a :class:`str` object.

        The result reports if the C extension is used or not.
        e.g. `1.0.0 (C extension active - AVX2)`
        """
        if _has_extension:
            simd_name = None
            simd_flag = _get_simd_path()
            if simd_flag == 0:
                simd_name = 'No SIMD'
            elif simd_flag == 4:
                simd_name = 'SSSE3'
            elif simd_flag == 8:
                simd_name = 'SSE41'
            elif simd_flag == 16:
                simd_name = 'SSE42'
            elif simd_flag == 32:
                simd_name = 'AVX'
            elif simd_flag == 64:
                simd_name = 'AVX2'
            else:  # pragma: no branch
                simd_name = 'Unknown'  # pragma: no cover
            return __version__ + ' (C extension active - ' + simd_name + ')'
        return __version__ + ' (C extension inactive)'

    def standard_b64encode(s):
        """Encode bytes using the standard Base64 alphabet.

        Argument ``s`` is a :term:`bytes-like object` to encode.

        The result is returned as a :class:`bytes` object.
        """
        return b64encode(s)

    def standard_b64decode(s):
        """Decode bytes encoded with the standard Base64 alphabet.

        Argument ``s`` is a :term:`bytes-like object` or ASCII string to
        decode.

        The result is returned as a :class:`bytes` object.

        A :exc:`binascii.Error` is raised if the input is incorrectly padded.

        Characters that are not in the standard alphabet are discarded prior
        to the padding check.
        """
        return b64decode(s)

    def urlsafe_b64encode(s):
        """Encode bytes using the URL- and filesystem-safe Base64 alphabet.

        Argument ``s`` is a :term:`bytes-like object` to encode.

        The result is returned as a :class:`bytes` object.

        The alphabet uses '-' instead of '+' and '_' instead of '/'.
        """
        return b64encode(s, b'-_')

    def urlsafe_b64decode(s):
        """Decode bytes using the URL- and filesystem-safe Base64 alphabet.

        Argument ``s`` is a :term:`bytes-like object` or ASCII string to
        decode.

        The result is returned as a :class:`bytes` object.

        A :exc:`binascii.Error` is raised if the input is incorrectly padded.

        Characters that are not in the URL-safe base-64 alphabet, and are not
        a plus '+' or slash '/', are discarded prior to the padding check.

        The alphabet uses '-' instead of '+' and '_' instead of '/'.
        """
        return b64decode(s, b'-_')
