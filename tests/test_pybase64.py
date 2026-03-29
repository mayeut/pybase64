from __future__ import annotations

import base64
import sys
import warnings
from base64 import encodebytes as b64encodebytes
from binascii import Error as BinAsciiError
from enum import IntEnum
from typing import TYPE_CHECKING, Any

import pytest

import pybase64

if TYPE_CHECKING:
    from collections.abc import Callable

    from pybase64._typing import Buffer, Decode, Encode

from . import utils


def b64encode_as_string(
    s: Buffer,
    altchars: str | Buffer | None = None,
    *,
    wrapcol: int = 0,
) -> bytes:
    """Helper returning bytes instead of string for tests"""
    return pybase64.b64encode_as_string(s, altchars, wrapcol=wrapcol).encode("ascii")


def b64decode_as_bytearray(
    s: str | Buffer,
    altchars: str | Buffer | None = None,
    validate: bool = False,
) -> bytes:
    """Helper returning bytes instead of bytearray for tests"""
    return bytes(pybase64.b64decode_as_bytearray(s, altchars, validate))


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
    [
        b"A@@@@FG",
        None,
        BinAsciiError,
        "Incorrect padding|Non-base64 digit found|Only base64 data is allowed",
    ],
    ["ABC€", None, ValueError, "ASCII"],
    [3.0, None, TypeError, "bytes-like|buffer interface"],
    [memoryview(b"ABCDEFGH")[::2], None, BufferError, "contiguous"],
    ["\x80aaa", None, ValueError, "ASCII|Non-base64 digit found"],
    ["a\x80aa", None, ValueError, "ASCII|Non-base64 digit found"],
    ["aa\x80a", None, ValueError, "ASCII|Non-base64 digit found"],
    ["aaa\x80", None, ValueError, "ASCII|Non-base64 digit found"],
]
params_invalid_data_validate_values = [
    [b"\x00\x00\x00\x00", None, BinAsciiError, None],
    [b"A@@@@FGHIJKLMNOPQRSTUVWXYZabcdef", b"-_", BinAsciiError, None],
    [b"A@@@=FGHIJKLMNOPQRSTUVWXYZabcdef", b"-_", BinAsciiError, None],
    [b"A@@=@FGHIJKLMNOPQRSTUVWXYZabcdef", b"-_", BinAsciiError, None],
    [b"A@@@@FGHIJKLMNOPQRSTUVWXYZabcde@=", b"-_", BinAsciiError, None],
    [b"A@@@@FGHIJKLMNOPQRSTUVWXYZabcd@==", b"-_", BinAsciiError, None],
    [b"A@@@@FGH" * 10000, b"-_", BinAsciiError, None],
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
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            with pytest.raises(exception, match=match):
                dfn(vector, b"-_", validate=validate)
            dfn(vector, b"/+", validate=validate)


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
        "p4p": 1 | 2,  # SSE3
        "mrm": 1 | 2 | 4,  # SSSE3
        "pnr": 1 | 2 | 4 | 8,  # SSE41
        "nhm": 1 | 2 | 4 | 8 | 16,  # SSE42
        "snb": 1 | 2 | 4 | 8 | 16 | 32,  # AVX
        "hsw": 1 | 2 | 4 | 8 | 16 | 32 | 64,  # AVX2
        "skx": 1 | 2 | 4 | 8 | 16 | 32 | 64,  # AVX2
        "spr": 1 | 2 | 4 | 8 | 16 | 32 | 64 | 128,  # AVX512VBMI
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
