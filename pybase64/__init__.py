from ._version import __version__

try:
    __PYBASE64_SETUP__
except NameError:
    __PYBASE64_SETUP__ = False

# Only go on if not in setup.py
if not __PYBASE64_SETUP__:
    try:
        from ._pybase64 import b64encode
        from ._pybase64 import b64decode
        _has_extension = True
    except ImportError:
        from ._fallback import b64encode
        from ._fallback import b64decode
        _has_extension = False

    def get_version():
        if _has_extension:
            return __version__ + ' (C extension active)'
        return __version__ + ' (C extension inactive)'

    def standard_b64encode(s):
        """Encode bytes-like object s using the standard Base64 alphabet.
        The result is returned as a bytes object.
        """
        return b64encode(s)

    def standard_b64decode(s):
        """
        Decode bytes encoded with the standard Base64 alphabet.
        Argument s is a bytes-like object or ASCII string to decode.
        The result is returned as a bytes object.  A binascii.Error is raised
        if the input is incorrectly padded.  Characters that are not in the
        standard alphabet are discarded prior to the padding check.
        """
        return b64decode(s)

    def urlsafe_b64encode(s):
        """Encode bytes using the URL- and filesystem-safe Base64 alphabet.
        Argument s is a bytes-like object to encode.  The result is returned
        as a bytes object.  The alphabet uses '-' instead of '+' and '_'
        instead of '/'.
        """
        return b64encode(s, b'-_')

    def urlsafe_b64decode(s):
        """Decode bytes using the URL- and filesystem-safe Base64 alphabet.
        Argument s is a bytes-like object or ASCII string to decode.
        The result is returned as a bytes object.  A binascii.Error is raised
        if the input is incorrectly padded.  Characters that are not in the
        URL-safe base-64 alphabet, and are not a plus '+' or slash '/', are
        discarded prior to the padding check.
        The alphabet uses '-' instead of '+' and '_' instead of '/'.
        """
        return b64decode(s, b'-_')
