from __future__ import annotations

import os

import pytest

import pybase64

TYPE_CHECKING = False
if TYPE_CHECKING:
    from collections.abc import Iterator
    from typing import Any

has_extension = hasattr(pybase64, "_set_simd_path")
assert has_extension or os.environ.get("CIBUILDWHEEL", "0") == "0"

if has_extension:
    simd_runtime_paths = pybase64._get_simd_paths_runtime()  # type: ignore[attr-defined]
    simd_compile_paths = pybase64._get_simd_paths_compile()  # type: ignore[attr-defined]
else:
    simd_runtime_paths = simd_compile_paths = (pybase64._get_simd_path(),)  # type: ignore[attr-defined]

param_simd = pytest.mark.parametrize(
    "simd",
    simd_compile_paths,
    indirect=True,
)


@pytest.fixture
def simd(request: pytest.FixtureRequest) -> Iterator[str]:
    simd_path = request.param
    if not has_extension:
        assert simd_path == "py"
        yield simd_path
        return

    if simd_path not in simd_runtime_paths:
        pytest.skip(f"{simd_path!r} SIMD extension not available")  # pragma: no cover
    old_simd_path = pybase64._get_simd_path()  # type: ignore[attr-defined]
    pybase64._set_simd_path(simd_path)  # type: ignore[attr-defined]
    assert pybase64._get_simd_path() == simd_path  # type: ignore[attr-defined]
    yield simd_path
    pybase64._set_simd_path(old_simd_path)  # type: ignore[attr-defined]


def unused_args(*args: Any) -> None:  # noqa: ARG001
    return None
