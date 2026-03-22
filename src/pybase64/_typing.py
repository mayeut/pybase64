from __future__ import annotations

import sys
from typing import Literal, Protocol

if sys.version_info < (3, 12):
    from typing_extensions import Buffer
else:
    from collections.abc import Buffer

from pybase64._unspecified import _Unspecified


class Decode(Protocol):
    __name__: str
    __module__: str

    def __call__(
        self,
        s: str | Buffer,
        altchars: str | Buffer | None = None,
        validate: bool | Literal[_Unspecified.UNSPECIFIED] = _Unspecified.UNSPECIFIED,
        *,
        ignorechars: Buffer | Literal[_Unspecified.UNSPECIFIED] = _Unspecified.UNSPECIFIED,
    ) -> bytes: ...


class Encode(Protocol):
    __name__: str
    __module__: str

    def __call__(
        self,
        s: Buffer,
        altchars: Buffer | None = None,
        *,
        padded: bool = True,
        wrapcol: int = 0,
    ) -> bytes: ...


__all__ = ("Buffer", "Decode", "Encode")
