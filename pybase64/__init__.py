try:
    import _pybase64
    _has_extension = True
except ImportError:
    import base64
    _has_extension = False

"""
import base64
"""

def standard_b64encode(binarydata):
    if _has_extension:
        return _pybase64.encode(binarydata)
    else:
        return base64.standard_b64encode(binarydata)

def standard_b64decode(base64data):
    if _has_extension:
        return _pybase64.decode(base64data)
    else:
        return base64.standard_b64decode(base64data)
