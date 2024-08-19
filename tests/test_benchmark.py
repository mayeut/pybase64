import pytest

import pybase64

from . import utils

pytestmark = pytest.mark.benchmark


@pytest.fixture(scope="module")
def encode_data_full(request: pytest.FixtureRequest) -> bytes:
    if not request.config.getoption("--codspeed", default=False):
        pytest.skip("needs '--codspeed' to run")
    data_ = bytearray(i % 256 for i in range(1024 * 1024))
    data = bytearray(512 * 1024 * 1024)
    chunk_start = 0
    chunk_end = len(data_)
    while chunk_start < len(data):
        data[chunk_start:chunk_end] = data_
        chunk_start += len(data_)
        chunk_end += len(data_)
    return bytes(data)


@pytest.fixture(scope="module", params=(1, 1024, 1024 * 1024, 512 * 1024 * 1024))
def encode_data(request: pytest.FixtureRequest, encode_data_full: bytes) -> bytes:
    return encode_data_full[: request.param]


@pytest.fixture(scope="module")
def decode_data(encode_data: bytes) -> bytes:
    return pybase64.b64encode(encode_data)


@utils.param_simd
def test_encoding(simd: int, encode_data: bytearray) -> None:
    utils.unused_args(simd)  # simd is a parameter in order to control the order of tests
    pybase64.b64encode(encode_data)


@utils.param_simd
def test_decoding(simd: int, decode_data: bytearray) -> None:
    utils.unused_args(simd)  # simd is a parameter in order to control the order of tests
    pybase64.b64decode(decode_data, validate=True)
