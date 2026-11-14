from typing import Literal

from pybase64._typing import Buffer
from pybase64._unspecified import _Unspecified

def _get_simd_paths_compile() -> tuple[str, ...]: ...
def _get_simd_paths_runtime() -> tuple[str, ...]: ...
def _get_simd_path() -> str: ...
def _set_simd_path(path: str) -> None: ...
def b64decode(
    s: str | Buffer,
    altchars: str | Buffer | None = None,
    validate: bool | Literal[_Unspecified.UNSPECIFIED] = ...,
    *,
    padded: bool = True,
    ignorechars: Buffer | Literal[_Unspecified.UNSPECIFIED] = ...,
    canonical: bool = False,
) -> bytes: ...
def b64decode_as_bytearray(
    s: str | Buffer,
    altchars: str | Buffer | None = None,
    validate: bool | Literal[_Unspecified.UNSPECIFIED] = ...,
    *,
    padded: bool = True,
    ignorechars: Buffer | Literal[_Unspecified.UNSPECIFIED] = ...,
    canonical: bool = False,
) -> bytearray: ...
def b64encode(
    s: Buffer,
    altchars: str | Buffer | None = None,
    *,
    padded: bool = True,
    wrapcol: int = 0,
) -> bytes: ...
def b64encode_as_string(
    s: Buffer,
    altchars: str | Buffer | None = None,
    *,
    padded: bool = True,
    wrapcol: int = 0,
) -> str: ...
def encodebytes(s: Buffer) -> bytes: ...
