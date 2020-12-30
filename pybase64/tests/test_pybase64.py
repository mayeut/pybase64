import base64
from base64 import encodebytes as b64encodebytes
from binascii import Error as BinAsciiError

import pytest

import pybase64

try:
    from pybase64._pybase64 import (
        _get_simd_flags_compile,
        _get_simd_flags_runtime,
        _get_simd_path,
        _set_simd_path,
    )

    _has_extension = True
except ImportError:
    _has_extension = False


STD = 0
URL = 1
ALT1 = 2
ALT2 = 3
ALT3 = 4
name_lut = ["standard", "urlsafe", "alternative", "alternative2", "alternative3"]
altchars_lut = [b"+/", b"-_", b"@&", b"+,", b";/"]
enc_helper_lut = [
    pybase64.standard_b64encode,
    pybase64.urlsafe_b64encode,
    None,
    None,
    None,
]
ref_enc_helper_lut = [
    pybase64.standard_b64encode,
    pybase64.urlsafe_b64encode,
    None,
    None,
    None,
]
dec_helper_lut = [
    pybase64.standard_b64decode,
    pybase64.urlsafe_b64decode,
    None,
    None,
    None,
]
ref_dec_helper_lut = [
    base64.standard_b64decode,
    base64.urlsafe_b64decode,
    None,
    None,
    None,
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
    test_vectors_b64.append(
        [vector.translate(trans) for vector in test_vectors_b64_list]
    )

test_vectors_bin = []
for altchars in altchars_lut:
    test_vectors_bin.append(
        [base64.b64decode(vector, altchars) for vector in test_vectors_b64_list]
    )

compile_flags = [0]
runtime_flags = 0
if _has_extension:
    runtime_flags = _get_simd_flags_runtime()
    flags = _get_simd_flags_compile()
    for i in range(31):
        if flags & (1 << i):
            compile_flags += [(1 << i)]


def get_simd_name(simd_id):
    simd_name = None
    if _has_extension:
        simd_flag = compile_flags[simd_id]
        if simd_flag == 0:
            simd_name = "c"
        elif simd_flag == 4:
            simd_name = "ssse3"
        elif simd_flag == 8:
            simd_name = "sse41"
        elif simd_flag == 16:
            simd_name = "sse42"
        elif simd_flag == 32:
            simd_name = "avx"
        elif simd_flag == 64:
            simd_name = "avx2"
        else:  # pragma: no branch
            simd_name = "unk"  # pragma: no cover
    else:
        simd_name = "py"
    return simd_name


def simd_setup(simd_id):
    if _has_extension:
        flag = compile_flags[simd_id]
        if flag != 0 and not flag & runtime_flags:  # pragma: no branch
            pytest.skip("SIMD extension not available")  # pragma: no cover
        _set_simd_path(flag)
        assert _get_simd_path() == flag
    else:
        assert 0 == simd_id


param_vector = pytest.mark.parametrize("vector_id", range(len(test_vectors_bin[0])))


param_validate = pytest.mark.parametrize(
    "validate", [False, True], ids=["novalidate", "validate"]
)


param_altchars = pytest.mark.parametrize(
    "altchars_id", [STD, URL, ALT1, ALT2, ALT3], ids=lambda x: name_lut[x]
)


param_altchars_helper = pytest.mark.parametrize(
    "altchars_id", [STD, URL], ids=lambda x: name_lut[x]
)


param_simd = pytest.mark.parametrize(
    "simd", range(len(compile_flags)), ids=lambda x: get_simd_name(x), indirect=True
)


param_encode_functions = pytest.mark.parametrize(
    "efn, ecast",
    [
        (pybase64.b64encode, lambda x: x),
        (pybase64.b64encode_as_string, lambda x: x.encode("ascii")),
    ],
)


param_decode_functions = pytest.mark.parametrize(
    "dfn, dcast",
    [
        (pybase64.b64decode, lambda x: x),
        (pybase64.b64decode_as_bytearray, lambda x: bytes(x)),
    ],
)


@pytest.fixture
def simd(request):
    simd_setup(request.param)
    return request.param


@param_simd
def test_version(simd):
    assert pybase64.get_version().startswith(pybase64.__version__)


@param_simd
@param_vector
@param_altchars_helper
def test_enc_helper(altchars_id, vector_id, simd):
    vector = test_vectors_bin[altchars_id][vector_id]
    test = enc_helper_lut[altchars_id](vector)
    base = ref_enc_helper_lut[altchars_id](vector)
    assert test == base


@param_simd
@param_vector
@param_altchars_helper
def test_dec_helper(altchars_id, vector_id, simd):
    vector = test_vectors_b64[altchars_id][vector_id]
    test = dec_helper_lut[altchars_id](vector)
    base = ref_dec_helper_lut[altchars_id](vector)
    assert test == base


@param_simd
@param_vector
@param_altchars_helper
def test_dec_helper_unicode(altchars_id, vector_id, simd):
    vector = test_vectors_b64[altchars_id][vector_id]
    test = dec_helper_lut[altchars_id](str(vector, "utf-8"))
    base = ref_dec_helper_lut[altchars_id](str(vector, "utf-8"))
    assert test == base


@param_simd
@param_vector
@param_altchars_helper
def test_rnd_helper(altchars_id, vector_id, simd):
    vector = test_vectors_b64[altchars_id][vector_id]
    test = dec_helper_lut[altchars_id](vector)
    test = enc_helper_lut[altchars_id](test)
    assert test == vector


@param_simd
@param_vector
@param_altchars_helper
def test_rnd_helper_unicode(altchars_id, vector_id, simd):
    vector = test_vectors_b64[altchars_id][vector_id]
    test = dec_helper_lut[altchars_id](str(vector, "utf-8"))
    test = enc_helper_lut[altchars_id](test)
    assert test == vector


@param_simd
@param_vector
def test_encbytes(vector_id, simd):
    vector = test_vectors_bin[STD][vector_id]
    test = pybase64.encodebytes(vector)
    base = b64encodebytes(vector)
    assert test == base


@param_simd
@param_vector
@param_altchars
@param_encode_functions
def test_enc(efn, ecast, altchars_id, vector_id, simd):
    vector = test_vectors_bin[altchars_id][vector_id]
    altchars = altchars_lut[altchars_id]
    test = ecast(efn(vector, altchars))
    base = base64.b64encode(vector, altchars)
    assert test == base


@param_simd
@param_vector
@param_altchars
@param_validate
@param_decode_functions
def test_dec(dfn, dcast, altchars_id, vector_id, validate, simd):
    vector = test_vectors_b64[altchars_id][vector_id]
    altchars = altchars_lut[altchars_id]
    if validate:
        base = base64.b64decode(vector, altchars, validate)
    else:
        base = base64.b64decode(vector, altchars)
    test = dcast(dfn(vector, altchars, validate))
    assert test == base


@param_simd
@param_vector
@param_altchars
@param_validate
@param_decode_functions
def test_dec_unicode(dfn, dcast, altchars_id, vector_id, validate, simd):
    vector = test_vectors_b64[altchars_id][vector_id]
    vector = str(vector, "utf-8")
    altchars = altchars_lut[altchars_id]
    if altchars_id == STD:
        altchars = None
    else:
        altchars = str(altchars, "utf-8")
    if validate:
        base = base64.b64decode(vector, altchars, validate)
    else:
        base = base64.b64decode(vector, altchars)
    test = dcast(dfn(vector, altchars, validate))
    assert test == base


@param_simd
@param_vector
@param_altchars
@param_validate
@param_encode_functions
@param_decode_functions
def test_rnd(dfn, dcast, efn, ecast, altchars_id, vector_id, validate, simd):
    vector = test_vectors_b64[altchars_id][vector_id]
    altchars = altchars_lut[altchars_id]
    test = dcast(dfn(vector, altchars, validate))
    test = ecast(efn(test, altchars))
    assert test == vector


@param_simd
@param_vector
@param_altchars
@param_validate
@param_encode_functions
@param_decode_functions
def test_rnd_unicode(dfn, dcast, efn, ecast, altchars_id, vector_id, validate, simd):
    vector = test_vectors_b64[altchars_id][vector_id]
    altchars = altchars_lut[altchars_id]
    test = dcast(dfn(str(vector, "utf-8"), altchars, validate))
    test = ecast(efn(test, altchars))
    assert test == vector


@param_simd
@param_vector
@param_altchars
@param_validate
@param_decode_functions
def test_invalid_padding_dec(dfn, dcast, altchars_id, vector_id, validate, simd):
    vector = test_vectors_b64[altchars_id][vector_id][1:]
    if len(vector) > 0:
        altchars = altchars_lut[altchars_id]
        with pytest.raises(BinAsciiError):
            dfn(vector, altchars, validate)


params_invalid_altchars = [
    [b"", AssertionError],
    [b"-", AssertionError],
    [b"-__", AssertionError],
    [3.0, TypeError],
    ["-€", ValueError],
]
params_invalid_altchars = pytest.mark.parametrize(
    "altchars,exception",
    params_invalid_altchars,
    ids=[str(i) for i in range(len(params_invalid_altchars))],
)


@param_simd
@params_invalid_altchars
@param_encode_functions
def test_invalid_altchars_enc(efn, ecast, altchars, exception, simd):
    with pytest.raises(exception):
        efn(b"ABCD", altchars)


@param_simd
@params_invalid_altchars
@param_decode_functions
def test_invalid_altchars_dec(dfn, dcast, altchars, exception, simd):
    with pytest.raises(exception):
        dfn(b"ABCD", altchars)


@param_simd
@params_invalid_altchars
@param_decode_functions
def test_invalid_altchars_dec_validate(dfn, dcast, altchars, exception, simd):
    with pytest.raises(exception):
        dfn(b"ABCD", altchars, True)


params_invalid_data_novalidate = [
    [b"A@@@@FG", None, BinAsciiError],
    ["ABC€", None, ValueError],
    [3.0, None, TypeError],
]
params_invalid_data_validate = [
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
    "vector,altchars,exception",
    params_invalid_data_novalidate + params_invalid_data_validate,
    ids=[
        str(i)
        for i in range(
            len(params_invalid_data_novalidate) + len(params_invalid_data_validate)
        )
    ],
)
params_invalid_data_novalidate = pytest.mark.parametrize(
    "vector,altchars,exception",
    params_invalid_data_novalidate,
    ids=[str(i) for i in range(len(params_invalid_data_novalidate))],
)
params_invalid_data_validate = pytest.mark.parametrize(
    "vector,altchars,exception",
    params_invalid_data_validate,
    ids=[str(i) for i in range(len(params_invalid_data_validate))],
)


@param_simd
@params_invalid_data_novalidate
@param_decode_functions
def test_invalid_data_dec(dfn, dcast, vector, altchars, exception, simd):
    with pytest.raises(exception):
        dfn(vector, altchars)


@param_simd
@params_invalid_data_validate
@param_decode_functions
def test_invalid_data_dec_skip(dfn, dcast, vector, altchars, exception, simd):
    test = dcast(dfn(vector, altchars))
    base = base64.b64decode(vector, altchars)
    assert test == base


@param_simd
@params_invalid_data_all
@param_decode_functions
def test_invalid_data_dec_validate(dfn, dcast, vector, altchars, exception, simd):
    with pytest.raises(exception):
        dfn(vector, altchars, True)


@param_encode_functions
def test_invalid_data_enc_0(efn, ecast):
    with pytest.raises(TypeError):
        efn("this is a test")


@param_encode_functions
def test_invalid_args_enc_0(efn, ecast):
    with pytest.raises(TypeError):
        efn()


@param_decode_functions
def test_invalid_args_dec_0(dfn, dcast):
    with pytest.raises(TypeError):
        dfn()
