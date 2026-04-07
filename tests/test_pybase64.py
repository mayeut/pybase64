from __future__ import annotations

import base64
import re
import sys
import warnings
from base64 import encodebytes as b64encodebytes
from binascii import Error as BinAsciiError
from enum import IntEnum
from typing import TYPE_CHECKING, Any, Literal

import pytest

import pybase64
from pybase64._unspecified import _Unspecified

if TYPE_CHECKING:
    from collections.abc import Callable

    from pybase64._typing import Buffer, Decode, Encode

from . import utils


def b64encode_as_string(
    s: Buffer,
    altchars: str | Buffer | None = None,
    *,
    padded: bool = True,
    wrapcol: int = 0,
) -> bytes:
    """Helper returning bytes instead of string for tests"""
    return pybase64.b64encode_as_string(s, altchars, padded=padded, wrapcol=wrapcol).encode("ascii")


def b64decode_as_bytearray(
    s: str | Buffer,
    altchars: str | Buffer | None = None,
    validate: bool | Literal[_Unspecified.UNSPECIFIED] = _Unspecified.UNSPECIFIED,
    *,
    padded: bool = True,
    ignorechars: Buffer | Literal[_Unspecified.UNSPECIFIED] = _Unspecified.UNSPECIFIED,
) -> bytes:
    """Helper returning bytes instead of bytearray for tests"""
    kwargs: dict[str, Any] = {"padded": padded}
    if not isinstance(validate, _Unspecified):
        kwargs["validate"] = validate
    if not isinstance(ignorechars, _Unspecified):
        kwargs["ignorechars"] = ignorechars
    return bytes(pybase64.b64decode_as_bytearray(s, altchars, **kwargs))


param_encode_functions = pytest.mark.parametrize("efn", [pybase64.b64encode, b64encode_as_string])
param_decode_functions = pytest.mark.parametrize(
    "dfn",
    [pybase64.b64decode, b64decode_as_bytearray],
)


class AltCharsId(IntEnum):
    STD = 0
    URL = 1
    ALT1 = 2
    ALT2 = 3
    ALT3 = 4


altchars_lut = [b"+/", b"-_", b",+", b"/;", b"/+"]
enc_helper_lut: list[Callable[[Buffer], bytes]] = [
    pybase64.standard_b64encode,
    pybase64.urlsafe_b64encode,
]
ref_enc_helper_lut: list[Callable[[Buffer], bytes]] = [
    base64.standard_b64encode,
    base64.urlsafe_b64encode,
]
dec_helper_lut: list[Callable[[str | Buffer], bytes]] = [
    pybase64.standard_b64decode,
    pybase64.urlsafe_b64decode,
]
ref_dec_helper_lut: list[Callable[[str | Buffer], bytes]] = [
    base64.standard_b64decode,
    base64.urlsafe_b64decode,
]

std = b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/A"
std = std * (32 * 16)
std_len_minus_12 = len(std) - 12

test_vectors_b64_list = [
    # rfc4648 test vectors
    b"",
    b"Zg==",
    b"Zm8=",
    b"Zm9v",
    b"Zm9vYg==",
    b"Zm9vYmE=",
    b"Zm9vYmFy",
    # custom test vectors
    std[std_len_minus_12:],
    std,
    std[:72],
    std[:76],
    std[:80],
    std[:148],
    std[:152],
    std[:156],
]

test_vectors_b64 = []
for altchars in altchars_lut:
    trans = bytes.maketrans(b"+/", altchars)
    test_vectors_b64.append([vector.translate(trans) for vector in test_vectors_b64_list])

test_vectors_bin = []
for altchars_id in AltCharsId:
    altchars = altchars_lut[altchars_id]
    vectors = test_vectors_b64[altchars_id]
    test_vectors_bin.append(
        [base64.b64decode(vector, altchars) for vector in vectors],
    )


param_vector = pytest.mark.parametrize("vector_id", range(len(test_vectors_bin[0])))


param_validate = pytest.mark.parametrize("validate", [False, True], ids=["novalidate", "validate"])


param_altchars = pytest.mark.parametrize("altchars_id", list(AltCharsId), ids=lambda x: x.name)


param_altchars_helper = pytest.mark.parametrize(
    "altchars_id",
    [AltCharsId.STD, AltCharsId.URL],
    ids=lambda x: x.name,
)


@utils.param_simd
def test_version(simd: int) -> None:
    utils.unused_args(simd)  # simd is a parameter in order to control the order of tests
    assert pybase64.get_version().startswith(pybase64.__version__)


@utils.param_simd
@param_vector
@param_altchars_helper
def test_enc_helper(altchars_id: int, vector_id: int, simd: int) -> None:
    utils.unused_args(simd)  # simd is a parameter in order to control the order of tests
    vector = test_vectors_bin[altchars_id][vector_id]
    test = enc_helper_lut[altchars_id](vector)
    base = ref_enc_helper_lut[altchars_id](vector)
    assert test == base


@utils.param_simd
@param_vector
@param_altchars_helper
def test_dec_helper(altchars_id: int, vector_id: int, simd: int) -> None:
    utils.unused_args(simd)  # simd is a parameter in order to control the order of tests
    vector = test_vectors_b64[altchars_id][vector_id]
    test = dec_helper_lut[altchars_id](vector)
    base = ref_dec_helper_lut[altchars_id](vector)
    assert test == base


@utils.param_simd
@param_vector
@param_altchars_helper
def test_dec_helper_unicode(altchars_id: int, vector_id: int, simd: int) -> None:
    utils.unused_args(simd)  # simd is a parameter in order to control the order of tests
    vector = test_vectors_b64[altchars_id][vector_id]
    test = dec_helper_lut[altchars_id](str(vector, "utf-8"))
    base = ref_dec_helper_lut[altchars_id](str(vector, "utf-8"))
    assert test == base


@utils.param_simd
@param_vector
@param_altchars_helper
def test_rnd_helper(altchars_id: int, vector_id: int, simd: int) -> None:
    utils.unused_args(simd)  # simd is a parameter in order to control the order of tests
    vector = test_vectors_b64[altchars_id][vector_id]
    test = dec_helper_lut[altchars_id](vector)
    test = enc_helper_lut[altchars_id](test)
    assert test == vector


@utils.param_simd
@param_vector
@param_altchars_helper
def test_rnd_helper_unicode(altchars_id: int, vector_id: int, simd: int) -> None:
    utils.unused_args(simd)  # simd is a parameter in order to control the order of tests
    vector = test_vectors_b64[altchars_id][vector_id]
    test = dec_helper_lut[altchars_id](str(vector, "utf-8"))
    test = enc_helper_lut[altchars_id](test)
    assert test == vector


@utils.param_simd
@param_vector
def test_encbytes(vector_id: int, simd: int) -> None:
    utils.unused_args(simd)  # simd is a parameter in order to control the order of tests
    vector = test_vectors_bin[AltCharsId.STD][vector_id]
    test = pybase64.encodebytes(vector)
    base = b64encodebytes(vector)
    assert test == base


@utils.param_simd
@param_vector
@param_altchars
@param_encode_functions
def test_enc(efn: Encode, altchars_id: int, vector_id: int, simd: int) -> None:
    utils.unused_args(simd)  # simd is a parameter in order to control the order of tests
    vector = test_vectors_bin[altchars_id][vector_id]
    altchars = altchars_lut[altchars_id]
    test = efn(vector, altchars)
    base = base64.b64encode(vector, altchars)
    assert test == base


@utils.param_simd
@param_vector
@param_altchars
@param_validate
@param_decode_functions
def test_dec(dfn: Decode, altchars_id: int, vector_id: int, validate: bool, simd: int) -> None:
    utils.unused_args(simd)  # simd is a parameter in order to control the order of tests
    vector = test_vectors_b64[altchars_id][vector_id]
    altchars = altchars_lut[altchars_id]
    if validate:
        base = base64.b64decode(vector, altchars, validate)
    else:
        base = base64.b64decode(vector, altchars)
    test = dfn(vector, altchars, validate)
    assert test == base


@utils.param_simd
@param_vector
@param_altchars
@param_validate
@param_decode_functions
def test_dec_unicode(
    dfn: Decode,
    altchars_id: int,
    vector_id: int,
    validate: bool,
    simd: int,
) -> None:
    utils.unused_args(simd)  # simd is a parameter in order to control the order of tests
    vector = str(test_vectors_b64[altchars_id][vector_id], "utf-8")
    altchars = None if altchars_id == AltCharsId.STD else str(altchars_lut[altchars_id], "utf-8")
    if validate:
        base = base64.b64decode(vector, altchars, validate)
    else:
        base = base64.b64decode(vector, altchars)
    test = dfn(vector, altchars, validate)
    assert test == base


@utils.param_simd
@param_vector
@param_altchars
@param_validate
@param_encode_functions
@param_decode_functions
def test_rnd(
    dfn: Decode,
    efn: Encode,
    altchars_id: int,
    vector_id: int,
    validate: bool,
    simd: int,
) -> None:
    utils.unused_args(simd)  # simd is a parameter in order to control the order of tests
    vector = test_vectors_b64[altchars_id][vector_id]
    altchars = altchars_lut[altchars_id]
    test = dfn(vector, altchars, validate)
    test = efn(test, altchars)
    assert test == vector


@utils.param_simd
@param_vector
@param_altchars
@param_validate
@param_encode_functions
@param_decode_functions
def test_rnd_unicode(
    dfn: Decode,
    efn: Encode,
    altchars_id: int,
    vector_id: int,
    validate: bool,
    simd: int,
) -> None:
    utils.unused_args(simd)  # simd is a parameter in order to control the order of tests
    vector = test_vectors_b64[altchars_id][vector_id]
    altchars = altchars_lut[altchars_id]
    test = dfn(str(vector, "utf-8"), altchars, validate)
    test = efn(test, altchars)
    assert test == vector


@utils.param_simd
@param_vector
@param_altchars
@param_validate
@param_decode_functions
def test_invalid_padding_dec(
    dfn: Decode,
    altchars_id: int,
    vector_id: int,
    validate: bool,
    simd: int,
) -> None:
    utils.unused_args(simd)  # simd is a parameter in order to control the order of tests
    vector = test_vectors_b64[altchars_id][vector_id][1:]
    if len(vector) > 0:
        altchars = altchars_lut[altchars_id]
        with pytest.raises(BinAsciiError):
            dfn(vector, altchars, validate)


params_invalid_altchars_values = [
    [b"", ValueError],
    [b"-", ValueError],
    [b"-__", ValueError],
    [3.0, TypeError],
    ["-€", ValueError],
    [memoryview(b"- _")[::2], BufferError],
]
params_invalid_altchars = pytest.mark.parametrize(
    ("altchars", "exception"),
    params_invalid_altchars_values,
    ids=[str(i) for i in range(len(params_invalid_altchars_values))],
)


@utils.param_simd
@params_invalid_altchars
@param_encode_functions
def test_invalid_altchars_enc(
    efn: Encode,
    altchars: Any,
    exception: type[BaseException],
    simd: int,
) -> None:
    utils.unused_args(simd)  # simd is a parameter in order to control the order of tests
    with pytest.raises(exception):
        efn(b"ABCD", altchars)


@utils.param_simd
@params_invalid_altchars
@param_decode_functions
def test_invalid_altchars_dec(
    dfn: Decode,
    altchars: Any,
    exception: type[BaseException],
    simd: int,
) -> None:
    utils.unused_args(simd)  # simd is a parameter in order to control the order of tests
    with pytest.raises(exception):
        dfn(b"ABCD", altchars)


@utils.param_simd
@params_invalid_altchars
@param_decode_functions
def test_invalid_altchars_dec_validate(
    dfn: Decode,
    altchars: Any,
    exception: type[BaseException],
    simd: int,
) -> None:
    utils.unused_args(simd)  # simd is a parameter in order to control the order of tests
    with pytest.raises(exception):
        dfn(b"ABCD", altchars, validate=True)


params_invalid_data_novalidate_values = [
    [b"A@@@@FG", None, BinAsciiError, "Incorrect padding|Non-base64 digit found|Only base64 data"],
    ["ABC€", None, ValueError, "ASCII"],
    [3.0, None, TypeError, "bytes-like|buffer interface"],
    [memoryview(b"ABCDEFGH")[::2], None, BufferError, "contiguous"],
    ["a\x80aa", None, ValueError, "ASCII|Non-base64 digit found"],
    [b"a\x80aa", None, BinAsciiError, "Incorrect padding|Non-base64 digit found|Only base64 data"],
    ["a\x80aaa", None, ValueError, "ASCII|Non-base64 digit found"],
    [b"ab", None, BinAsciiError, "Incorrect padding|Non-base64 digit found"],
    [b"abc", None, BinAsciiError, "Incorrect padding|Non-base64 digit found"],
    [b"ab=", None, BinAsciiError, "Incorrect padding|Non-base64 digit found"],
    [b"ab==c", None, BinAsciiError, "Incorrect padding|Non-base64 digit found|Excess data after"],
]
params_invalid_data_validate_values = [
    [b"\x00\x00\x00\x00", None, BinAsciiError, None],
    [b"A@@@@FGHIJKLMNOPQRSTUVWXYZabcdef", b"-_", BinAsciiError, None],
    [b"A@@@=FGHIJKLMNOPQRSTUVWXYZabcdef", b"-_", BinAsciiError, None],
    [b"A@@=@FGHIJKLMNOPQRSTUVWXYZabcdef", b"-_", BinAsciiError, None],
    [b"A@@@@FGHIJKLMNOPQRSTUVWXYZabcde@=", b"-_", BinAsciiError, None],
    [b"A@@@@FGHIJKLMNOPQRSTUVWXYZabcd@==", b"-_", BinAsciiError, None],
    [b"A@@@@FGH" * 10000, b"-_", BinAsciiError, None],
    [b"a\x80aaa", None, BinAsciiError, "Incorrect padding|Non-base64 digit found|Only base64 data"],
]
params_invalid_data_all = pytest.mark.parametrize(
    ("vector", "altchars", "exception", "match"),
    params_invalid_data_novalidate_values + params_invalid_data_validate_values,
    ids=[
        str(i)
        for i in range(
            len(params_invalid_data_novalidate_values) + len(params_invalid_data_validate_values),
        )
    ],
)
params_invalid_data_novalidate = pytest.mark.parametrize(
    ("vector", "altchars", "exception", "match"),
    params_invalid_data_novalidate_values,
    ids=[str(i) for i in range(len(params_invalid_data_novalidate_values))],
)
params_invalid_data_validate = pytest.mark.parametrize(
    ("vector", "altchars", "exception", "match"),
    params_invalid_data_validate_values,
    ids=[str(i) for i in range(len(params_invalid_data_validate_values))],
)


@utils.param_simd
@params_invalid_data_novalidate
@param_decode_functions
def test_invalid_data_dec(
    dfn: Decode,
    vector: Any,
    altchars: Buffer | None,
    exception: type[BaseException],
    match: str | None,
    simd: int,
) -> None:
    utils.unused_args(simd)  # simd is a parameter in order to control the order of tests
    with pytest.raises(exception, match=match):
        dfn(vector, altchars)


@utils.param_simd
@params_invalid_data_validate
@param_decode_functions
def test_invalid_data_dec_skip(
    dfn: Decode,
    vector: Any,
    altchars: Buffer | None,
    exception: type[BaseException],
    match: str | None,
    simd: int,
) -> None:
    utils.unused_args(
        exception,
        match,
        simd,
    )  # simd is a parameter in order to control the order of tests
    test = dfn(vector, altchars)
    if sys.implementation.name == "graalpy" and vector.startswith((b"A@@@=F", b"A@@=@")):
        pytest.xfail(reason="graalpy fails decoding those entries")  # pragma: no cover
    base = base64.b64decode(vector, altchars)
    assert test == base


@utils.param_simd
@params_invalid_data_all
@param_decode_functions
def test_invalid_data_dec_validate(
    dfn: Decode,
    vector: Any,
    altchars: Buffer | None,
    exception: type[BaseException],
    match: str | None,
    simd: int,
) -> None:
    utils.unused_args(simd)  # simd is a parameter in order to control the order of tests
    with pytest.raises(exception, match=match):
        dfn(vector, altchars, validate=True)


@utils.param_simd
@params_invalid_data_all
@param_decode_functions
def test_invalid_data_dec_ignorechars_empty(
    dfn: Decode,
    vector: Any,
    altchars: Buffer | None,
    exception: type[BaseException],
    match: str | None,
    simd: int,
) -> None:
    utils.unused_args(simd)  # simd is a parameter in order to control the order of tests
    with pytest.raises(exception, match=match):
        dfn(vector, altchars, ignorechars=b"")


@utils.param_simd
@param_validate
@param_decode_functions
def test_warning_data_dec(
    dfn: Decode,
    validate: bool,
    simd: int,
) -> None:
    utils.unused_args(simd)  # simd is a parameter in order to control the order of tests
    exception, match = {
        True: (DeprecationWarning, r"invalid character.*will be an error in future"),
        False: (FutureWarning, r"invalid character.*will be discarded in future"),
    }[validate]
    # src_slice in the C code is 16 * 1024 = 16384 bytes; the large vector tests
    # that has_bad_char is accumulated (not overwritten) across chunks so that a
    # '+' or '/' in the first chunk is not silently lost when later chunks are clean.
    src_slice = 16 * 1024
    vector_ = "+/" + "A" * (src_slice - 2) + "AAAA"
    for vector in [vector_, vector_[:4]]:
        with pytest.warns(exception, match=match):
            dfn(vector, b"-_", validate=validate)
        with pytest.warns(exception, match=match):
            dfn(vector, b"+_", validate=validate)
        with pytest.warns(exception, match=match):
            dfn(vector, b"-+", validate=validate)
        with pytest.warns(exception, match=match):
            dfn(vector, b"/_", validate=validate)
        with pytest.warns(exception, match=match):
            dfn(vector, b"-/", validate=validate)
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            with pytest.raises(exception, match=match):
                dfn(vector, b"-_", validate=validate)
            dfn(vector, b"/+", validate=validate)


@utils.param_simd
@param_decode_functions
def test_altchars_translation(
    dfn: Decode,
    simd: int,
) -> None:
    utils.unused_args(simd)  # simd is a parameter in order to control the order of tests
    # src_slice in the C code is 16 * 1024 = 16384 bytes; the large vector tests
    # that has_bad_char is accumulated (not overwritten) across chunks so that a
    # '+' or '/' in the first chunk is not silently lost when later chunks are clean.
    src_slice = 16 * 1024
    vector_ = "+/" + "A" * (src_slice - 2) + "AAAA"
    for vector in [vector_, vector_[:4]]:
        with pytest.raises(BinAsciiError):
            dfn(vector, b"-_", ignorechars=b"")
        with pytest.raises(BinAsciiError):
            dfn(vector, b"+_", ignorechars=b"")
        with pytest.raises(BinAsciiError):
            dfn(vector, b"-+", ignorechars=b"")
        with pytest.raises(BinAsciiError):
            dfn(vector, b"/_", ignorechars=b"")
        with pytest.raises(BinAsciiError):
            dfn(vector, b"-/", ignorechars=b"")
        dfn(vector, b"/+", ignorechars=b"")


params_invalid_data_enc_values = [
    ["this is a test", TypeError],
    [memoryview(b"abcd")[::2], BufferError],
]
params_invalid_data_encodebytes_values = [
    *params_invalid_data_enc_values,
    [memoryview(b"abcd").cast("B", (2, 2)), TypeError],
    [memoryview(b"abcd").cast("I"), TypeError],
]
params_invalid_data_enc = pytest.mark.parametrize(
    ("vector", "exception"),
    params_invalid_data_enc_values,
    ids=[str(i) for i in range(len(params_invalid_data_enc_values))],
)
params_invalid_data_encodebytes = pytest.mark.parametrize(
    ("vector", "exception"),
    params_invalid_data_encodebytes_values,
    ids=[str(i) for i in range(len(params_invalid_data_encodebytes_values))],
)


@params_invalid_data_enc
@param_encode_functions
def test_invalid_data_enc(efn: Encode, vector: Any, exception: type[BaseException]) -> None:
    with pytest.raises(exception):
        efn(vector)


@params_invalid_data_encodebytes
def test_invalid_data_encodebytes(vector: Any, exception: type[BaseException]) -> None:
    with pytest.raises(exception):
        pybase64.encodebytes(vector)


@param_encode_functions
def test_invalid_args_enc_0(efn: Encode) -> None:
    with pytest.raises(TypeError):
        efn()  # type: ignore[call-arg]


@param_decode_functions
def test_invalid_args_dec_0(dfn: Decode) -> None:
    with pytest.raises(TypeError):
        dfn()  # type: ignore[call-arg]


def test_flags(request: pytest.FixtureRequest) -> None:
    cpu = request.config.getoption("--sde-cpu", skip=True)
    assert {
        "p4p": 0,  # no simd
        "mrm": 4,  # SSSE3
        "pnr": 4 | 8,  # SSE41
        "nhm": 4 | 8 | 16,  # SSE42
        "snb": 4 | 8 | 16 | 32,  # AVX
        "hsw": 4 | 8 | 16 | 32 | 64,  # AVX2
        "skx": 4 | 8 | 16 | 32 | 64,  # AVX2
        "spr": 4 | 8 | 16 | 32 | 64 | 128,  # AVX512VBMI
        "neon": 65536,  # NEON
    }[cpu] == utils.runtime_flags


@param_encode_functions
def test_enc_multi_dimensional(efn: Encode) -> None:
    source = b"abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUV"
    vector = memoryview(source).cast("B", (4, len(source) // 4))
    assert vector.c_contiguous
    test = efn(vector, None)
    base = base64.b64encode(source)
    assert test == base


@param_decode_functions
def test_dec_multi_dimensional(dfn: Decode) -> None:
    source = b"abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUV"
    vector = memoryview(source).cast("B", (4, len(source) // 4))
    assert vector.c_contiguous
    test = dfn(vector, None)
    base = base64.b64decode(source)
    assert test == base


if sys.version_info >= (3, 15):
    _ref_b64encode_wrapcol = base64.b64encode
else:

    def _ref_b64encode_wrapcol(s: bytes, altchars: bytes | None, *, wrapcol: int) -> bytes:
        """Reference implementation of b64encode with wrapcol."""
        encoded = base64.b64encode(s, altchars)
        if wrapcol == 0 or not encoded:
            return encoded
        effective_wrapcol = (wrapcol // 4) * 4 or 4
        return b"\n".join(
            encoded[i : i + effective_wrapcol] for i in range(0, len(encoded), effective_wrapcol)
        )


@utils.param_simd
@param_vector
@param_altchars_helper
@pytest.mark.parametrize("wrapcol", [0, 1, 76, 77, 78, 79, 80])
@param_encode_functions
def test_enc_wrapcol(
    efn: Encode,
    altchars_id: int,
    vector_id: int,
    wrapcol: int,
    simd: int,
) -> None:
    utils.unused_args(simd)
    vector = test_vectors_bin[altchars_id][vector_id]
    altchars = altchars_lut[altchars_id]
    test = efn(vector, altchars, wrapcol=wrapcol)
    base = _ref_b64encode_wrapcol(vector, altchars, wrapcol=wrapcol)
    assert test == base


@utils.param_simd
@param_vector
def test_enc_wrapcol_matches_encodebytes(vector_id: int, simd: int) -> None:
    utils.unused_args(simd)
    vector = test_vectors_bin[AltCharsId.STD][vector_id]
    enc = pybase64.b64encode(vector, wrapcol=76)
    assert pybase64.encodebytes(vector) == enc + (b"\n" if enc else b"")


@utils.param_simd
def test_enc_wrapcol_empty(simd: int) -> None:
    utils.unused_args(simd)
    assert pybase64.b64encode(b"", wrapcol=76) == b""
    assert pybase64.b64encode_as_string(b"", wrapcol=76) == ""
    assert pybase64.encodebytes(b"") == b""


@utils.param_simd
def test_enc_wrapcol_invalid(simd: int) -> None:
    utils.unused_args(simd)
    with pytest.raises(ValueError, match="wrapcol must be >= 0"):
        pybase64.b64encode(b"test", wrapcol=-1)
    with pytest.raises(ValueError, match="wrapcol must be >= 0"):
        pybase64.b64encode_as_string(b"test", wrapcol=-1)


@utils.param_simd
def test_enc_wrapcol_limit(simd: int) -> None:
    utils.unused_args(simd)
    vector = b"A" * ((76 // 4) * 3)
    encoded = pybase64.b64encode(vector, wrapcol=76)
    assert len(encoded) == 76
    assert (encoded + b"\n") == pybase64.encodebytes(vector)


@param_encode_functions
@pytest.mark.parametrize(
    ("vector", "expected"),
    [(b"", b""), (b"a", b"YQ"), (b"ab", b"YWI"), (b"abc", b"YWJj")],
)
@utils.param_simd
def test_b64encode_padded(efn: Encode, vector: bytes, expected: bytes, simd: int) -> None:
    utils.unused_args(simd)
    assert efn(vector, padded=False) == expected


@param_decode_functions
@pytest.mark.parametrize(
    ("vector", "expected", "padded_exc"),
    [
        (b"", b"", False),
        (b"YQ==", b"a", False),
        (b"YQ", b"a", True),
        (b"YQ=", b"a", True),
        (b"YWI=", b"ab", False),
        (b"YWI", b"ab", True),
        (b"YWJj", b"abc", False),
        (b"=YWJj", b"abc", False),
        (b"Y=WJj", b"abc", False),
        (b"YW=Jj", b"abc", False),
        (b"YWJ=j", b"abc", False),
    ],
)
@utils.param_simd
def test_b64decode_padded(
    dfn: Decode,
    vector: bytes,
    expected: bytes,
    padded_exc: bool,
    simd: int,
) -> None:
    utils.unused_args(simd)
    if b"=" in vector:
        with pytest.raises(BinAsciiError):
            dfn(vector, padded=False, validate=True)
        with pytest.raises(BinAsciiError):
            dfn(vector, padded=False, ignorechars=b"")
    else:
        assert dfn(vector, padded=False, validate=True) == expected
        assert dfn(vector, padded=False, ignorechars=b"") == expected
    if padded_exc:
        with pytest.raises(BinAsciiError):
            dfn(vector, padded=True)
    else:
        assert dfn(vector, padded=True) == expected
    assert dfn(vector, padded=False) == expected
    assert dfn(vector, padded=False, ignorechars=b"=") == expected


@pytest.mark.parametrize(
    ("vector", "expected"),
    [(b"", b""), (b"a", b"YQ"), (b"ab", b"YWI"), (b"abc", b"YWJj")],
)
@utils.param_simd
def test_urlsafe_b64encode_padded(vector: bytes, expected: bytes, simd: int) -> None:
    utils.unused_args(simd)
    assert pybase64.urlsafe_b64encode(vector, padded=False) == expected


@pytest.mark.parametrize(
    ("vector", "expected"),
    [(b"", b""), (b"YQ", b"a"), (b"YQ=", b"a"), (b"YWI", b"ab"), (b"YWJj", b"abc")],
)
@utils.param_simd
def test_urlsafe_b64decode_padded(vector: bytes, expected: bytes, simd: int) -> None:
    utils.unused_args(simd)
    if (len(vector) % 4) != 0:
        with pytest.raises(BinAsciiError, match="Incorrect padding"):
            pybase64.urlsafe_b64decode(vector, padded=True)
    assert pybase64.urlsafe_b64decode(vector, padded=False) == expected


@utils.param_simd
def test_ignorechars_altchars_limit(simd: int) -> None:
    utils.unused_args(simd)
    assert pybase64.b64decode(b"/----", altchars=b"-+", ignorechars=b"/") == b"\xfb\xef\xbe"
    assert pybase64.b64decode(b"/----", altchars=b"+-", ignorechars=b"/") == b"\xff\xff\xff"
    assert pybase64.b64decode(b"+----", altchars=b"-/", ignorechars=b"+") == b"\xfb\xef\xbe"
    assert pybase64.b64decode(b"+----", altchars=b"/-", ignorechars=b"+") == b"\xff\xff\xff"
    assert pybase64.b64decode(b"+/+/", altchars=b"/+", ignorechars=b"") == b"\xff\xef\xfe"
    assert pybase64.b64decode(b"/+/+", altchars=b"+/", ignorechars=b"") == b"\xff\xef\xfe"


@utils.param_simd
def test_ignorechars_invalid(simd: int) -> None:
    utils.unused_args(simd)
    with pytest.raises(TypeError):
        pybase64.b64decode(b"", ignorechars="")  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        pybase64.b64decode(b"", ignorechars=[])  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        pybase64.b64decode(b"", ignorechars=None)  # type: ignore[arg-type]
    msg = re.escape("validate must be True or unspecified when ignorechars is specified")
    with pytest.raises(ValueError, match=msg):
        pybase64.b64decode(b"", validate=False, ignorechars=b"")
    with pytest.raises(ValueError, match="ASCII"):
        pybase64.b64decode("YW\x80Jj", ignorechars=b"\x80")


@param_decode_functions
@utils.param_simd
def test_ignorechars(dfn: Decode, simd: int) -> None:
    utils.unused_args(simd)  # simd is a parameter in order to control the order of tests
    assert dfn(b"YW\nJj", ignorechars=b"\n") == b"abc"
    assert dfn(b"YW\nJj", ignorechars=bytearray(b"\n")) == b"abc"
    assert dfn(b"YW\nJj", ignorechars=memoryview(b"\n")) == b"abc"
    assert dfn(b"{YWJj", ignorechars=b"{}") == b"abc"
    assert dfn(b"Y}WJj", ignorechars=b"{}") == b"abc"
    assert dfn(b"YW{Jj", ignorechars=b"{}") == b"abc"
    assert dfn(b"YWJ}j", ignorechars=b"{}") == b"abc"
    # base64 alphabet ignored in ignorechars
    assert dfn(b"YWJj", ignorechars=b"Y") == b"abc"
    assert dfn(b"YW{Jj", ignorechars=b"Y{") == b"abc"
    # non ASCII
    assert dfn(b"YW\x80Jj", ignorechars=b"\x80") == b"abc"


@pytest.mark.parametrize(
    ("data", "ignorechars", "no_validation_expected_result", "ignorechars_expected_result"),
    [
        # excess padding
        (b"ab===", b"=", b"i", None),
        (b"ab====", b"=", b"i", None),
        (b"abc==", b"=", b"i\xb7", None),
        (b"abc===", b"=", b"i\xb7", None),
        (b"abc====", b"=", b"i\xb7", None),
        (b"abc=====", b"=", b"i\xb7", None),
        (b"abcd=", b"=", b"i\xb7\x1d", None),
        (b"abcd==", b"=", b"i\xb7\x1d", None),
        (b"abcd===", b"=", b"i\xb7\x1d", None),
        (b"abcd====", b"=", b"i\xb7\x1d", None),
        (b"abcd=====", b"=", b"i\xb7\x1d", None),
        (b"abcd=efgh", b"=", b"i\xb7\x1dy\xf8!", None),
        (b"abcd==efgh", b"=", b"i\xb7\x1dy\xf8!", None),
        (b"abcd===efgh", b"=", b"i\xb7\x1dy\xf8!", None),
        (b"abcd====efgh", b"=", b"i\xb7\x1dy\xf8!", None),
        (b"abcd=====efgh", b"=", b"i\xb7\x1dy\xf8!", None),
        (b"YWJj=", b"=", b"abc", None),
        # leading padding
        (b"=", b"=", b"", None),
        (b"==", b"=", b"", None),
        (b"===", b"=", b"", None),
        (b"====", b"=", b"", None),
        (b"=====", b"=", b"", None),
        (b"=abcd", b"=", b"i\xb7\x1d", None),
        (b"==abcd", b"=", b"i\xb7\x1d", None),
        (b"===abcd", b"=", b"i\xb7\x1d", None),
        (b"====abcd", b"=", b"i\xb7\x1d", None),
        (b"=====abcd", b"=", b"i\xb7\x1d", None),
        (b"[==", b"[=", b"", None),
        (b"=YWJj", b"=", b"abc", None),
        # invalid length
        (b"a=b==", b"=", b"i", None),
        (b"a=bc=", b"=", b"i\xb7", None),
        (b"a=bc==", b"=", b"i\xb7", None),
        (b"a=bcd", b"=", b"i\xb7\x1d", None),
        (b"a=bcd=", b"=", b"i\xb7\x1d", None),
        # discontinuous padding
        (b"ab=c=", b"=", b"i\xb7", None),
        (b"ab=cd", b"=", b"i\xb7\x1d", None),
        (b"ab=cd==", b"=", b"i\xb7\x1d", None),
        (b"Y=WJj", b"=", b"abc", None),
        (b"Y==WJj", b"=", b"abc", None),
        (b"YW=Jj", b"=", b"abc", None),
        # excess data
        (b"ab==cd", b"=", b"i\xb7\x1d", None),
        (b"abc=d", b"=", b"i\xb7\x1d", None),
        # invalid data
        (b"ab:(){:|:&};:==", b":;(){}|&", b"i", None),
        (b"\nab==", b"\n", b"i", None),
        (b"ab==\n", b"\n", b"i", None),
        (b"a\nb==", b"\n", b"i", None),
        (b"a\x00b==", b"\x00", b"i", None),
        (b"a\x00b==", b"@\x00", b"i", None),
        (b"\x00ab==", b"@\x00", b"i", None),
        (b"ab:==", b":", b"i", None),
        (b"ab=:=", b":", b"i", None),
        (b"ab==:", b":", b"i", None),
        (b"abc=:", b":", b"i\xb7", None),
        (b"@ab==", b":", b"i", BinAsciiError),
        (b"ab@==", b":", b"i", BinAsciiError),
        (b"ab=@=", b":", b"i", BinAsciiError),
        (b"abc@=", b":", b"i\xb7", BinAsciiError),
    ],
)
@utils.param_simd
def test_base64_dec_invalid_partial(
    data: bytes,
    ignorechars: bytes,
    no_validation_expected_result: bytes,
    ignorechars_expected_result: bytes | type | None,
    simd: int,
) -> None:
    utils.unused_args(simd)
    if ignorechars_expected_result is None:
        ignorechars_expected_result = no_validation_expected_result
    with pytest.raises(BinAsciiError):
        pybase64.b64decode(data, validate=True)
    with pytest.raises(BinAsciiError):
        pybase64.b64decode(data, validate=True, ignorechars=b"")
    ignorechars_no_equal = bytes(set(ignorechars) - set(b"="))
    ignorechars_has_equal = len(ignorechars_no_equal) != len(ignorechars)
    if ignorechars_has_equal:
        with pytest.raises(BinAsciiError):
            pybase64.b64decode(data, ignorechars=ignorechars_no_equal)
        if ignorechars_no_equal == b"":
            with pytest.raises(BinAsciiError):
                pybase64.b64decode(data, ignorechars=b"@")
    if isinstance(ignorechars_expected_result, type) and not ignorechars_has_equal:
        assert ignorechars_expected_result is BinAsciiError
        with pytest.raises(BinAsciiError):
            pybase64.b64decode(data, ignorechars=ignorechars)
    elif not ignorechars_has_equal:
        assert pybase64.b64decode(data, ignorechars=ignorechars) == ignorechars_expected_result
    assert pybase64.b64decode(data, validate=False) == no_validation_expected_result
    assert pybase64.b64decode(data) == no_validation_expected_result


def test_decode_edge_cases() -> None:
    with pytest.raises(BinAsciiError):
        pybase64.b64decode(b"YQ=)", validate=False)
    with pytest.raises(BinAsciiError):
        pybase64.b64decode(b"YQ=)", validate=True)
    with pytest.raises(BinAsciiError):
        pybase64.b64decode(b"YQ=)", padded=False, validate=True)
    assert pybase64.b64decode(b"YQ=)", padded=False) == b"a"
    assert pybase64.b64decode(b"YQ=)", padded=False, ignorechars=b")=") == b"a"
