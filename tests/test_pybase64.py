from __future__ import annotations

import base64
from base64 import encodebytes as b64encodebytes
from binascii import Error as BinAsciiError
from collections.abc import Callable
from enum import IntEnum
from typing import Any

import pytest

import pybase64
from pybase64._typing import Buffer, Decode, Encode

from . import utils


def b64encode_as_string(s: Buffer, altchars: str | Buffer | None = None) -> bytes:
    """helper returning bytes instead of string for tests"""
    return pybase64.b64encode_as_string(s, altchars).encode("ascii")


def b64decode_as_bytearray(
    s: str | Buffer, altchars: str | Buffer | None = None, validate: bool = False
) -> bytes:
    """helper returning bytes instead of bytearray for tests"""
    return bytes(pybase64.b64decode_as_bytearray(s, altchars, validate))


param_encode_functions = pytest.mark.parametrize("efn", [pybase64.b64encode, b64encode_as_string])
param_decode_functions = pytest.mark.parametrize(
    "dfn", [pybase64.b64decode, b64decode_as_bytearray]
)


class AltCharsId(IntEnum):
    STD = 0
    URL = 1
    ALT1 = 2
    ALT2 = 3
    ALT3 = 4


altchars_lut = [b"+/", b"-_", b"@&", b"+,", b";/"]
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
for altchars in altchars_lut:
    test_vectors_bin.append(
        [base64.b64decode(vector, altchars) for vector in test_vectors_b64_list]
    )


param_vector = pytest.mark.parametrize("vector_id", range(len(test_vectors_bin[0])))


param_validate = pytest.mark.parametrize("validate", [False, True], ids=["novalidate", "validate"])


param_altchars = pytest.mark.parametrize("altchars_id", list(AltCharsId), ids=lambda x: x.name)


param_altchars_helper = pytest.mark.parametrize(
    "altchars_id", [AltCharsId.STD, AltCharsId.URL], ids=lambda x: x.name
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
    dfn: Decode, altchars_id: int, vector_id: int, validate: bool, simd: int
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
    dfn: Decode, efn: Encode, altchars_id: int, vector_id: int, validate: bool, simd: int
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
    dfn: Decode, efn: Encode, altchars_id: int, vector_id: int, validate: bool, simd: int
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
    dfn: Decode, altchars_id: int, vector_id: int, validate: bool, simd: int
) -> None:
    utils.unused_args(simd)  # simd is a parameter in order to control the order of tests
    vector = test_vectors_b64[altchars_id][vector_id][1:]
    if len(vector) > 0:
        altchars = altchars_lut[altchars_id]
        with pytest.raises(BinAsciiError):
            dfn(vector, altchars, validate)


params_invalid_altchars_values = [
    [b"", AssertionError],
    [b"-", AssertionError],
    [b"-__", AssertionError],
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
    efn: Encode, altchars: Any, exception: type[BaseException], simd: int
) -> None:
    utils.unused_args(simd)  # simd is a parameter in order to control the order of tests
    with pytest.raises(exception):
        efn(b"ABCD", altchars)


@utils.param_simd
@params_invalid_altchars
@param_decode_functions
def test_invalid_altchars_dec(
    dfn: Decode, altchars: Any, exception: type[BaseException], simd: int
) -> None:
    utils.unused_args(simd)  # simd is a parameter in order to control the order of tests
    with pytest.raises(exception):
        dfn(b"ABCD", altchars)


@utils.param_simd
@params_invalid_altchars
@param_decode_functions
def test_invalid_altchars_dec_validate(
    dfn: Decode, altchars: Any, exception: type[BaseException], simd: int
) -> None:
    utils.unused_args(simd)  # simd is a parameter in order to control the order of tests
    with pytest.raises(exception):
        dfn(b"ABCD", altchars, True)


params_invalid_data_novalidate_values = [
    [b"A@@@@FG", None, BinAsciiError],
    ["ABC€", None, ValueError],
    [3.0, None, TypeError],
    [memoryview(b"ABCDEFGH")[::2], None, BufferError],
]
params_invalid_data_validate_values = [
    [b"\x00\x00\x00\x00", None, BinAsciiError],
    [b"A@@@@FGHIJKLMNOPQRSTUVWXYZabcdef", b"-_", BinAsciiError],
    [b"A@@@=FGHIJKLMNOPQRSTUVWXYZabcdef", b"-_", BinAsciiError],
    [b"A@@=@FGHIJKLMNOPQRSTUVWXYZabcdef", b"-_", BinAsciiError],
    [b"A@@@@FGHIJKLMNOPQRSTUVWXYZabcde@=", b"-_", BinAsciiError],
    [b"A@@@@FGHIJKLMNOPQRSTUVWXYZabcd@==", b"-_", BinAsciiError],
    [b"A@@@@FGH" * 10000, b"-_", BinAsciiError],
    # [std, b'-_', BinAsciiError],  TODO does no fail with base64 module
]
params_invalid_data_all = pytest.mark.parametrize(
    ("vector", "altchars", "exception"),
    params_invalid_data_novalidate_values + params_invalid_data_validate_values,
    ids=[
        str(i)
        for i in range(
            len(params_invalid_data_novalidate_values) + len(params_invalid_data_validate_values)
        )
    ],
)
params_invalid_data_novalidate = pytest.mark.parametrize(
    ("vector", "altchars", "exception"),
    params_invalid_data_novalidate_values,
    ids=[str(i) for i in range(len(params_invalid_data_novalidate_values))],
)
params_invalid_data_validate = pytest.mark.parametrize(
    ("vector", "altchars", "exception"),
    params_invalid_data_validate_values,
    ids=[str(i) for i in range(len(params_invalid_data_validate_values))],
)


@utils.param_simd
@params_invalid_data_novalidate
@param_decode_functions
def test_invalid_data_dec(
    dfn: Decode, vector: Any, altchars: Buffer | None, exception: type[BaseException], simd: int
) -> None:
    utils.unused_args(simd)  # simd is a parameter in order to control the order of tests
    with pytest.raises(exception):
        dfn(vector, altchars)


@utils.param_simd
@params_invalid_data_validate
@param_decode_functions
def test_invalid_data_dec_skip(
    dfn: Decode, vector: Any, altchars: Buffer | None, exception: type[BaseException], simd: int
) -> None:
    utils.unused_args(exception, simd)  # simd is a parameter in order to control the order of tests
    test = dfn(vector, altchars)
    base = base64.b64decode(vector, altchars)
    assert test == base


@utils.param_simd
@params_invalid_data_all
@param_decode_functions
def test_invalid_data_dec_validate(
    dfn: Decode, vector: Any, altchars: Buffer | None, exception: type[BaseException], simd: int
) -> None:
    utils.unused_args(simd)  # simd is a parameter in order to control the order of tests
    with pytest.raises(exception):
        dfn(vector, altchars, True)


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
