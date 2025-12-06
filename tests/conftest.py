from __future__ import annotations

import pytest

from . import utils

simd = utils.simd


@pytest.fixture(autouse=True)
def _autoskip_benchmark(request: pytest.FixtureRequest) -> None:
    marker = request.node.get_closest_marker("benchmark")
    benchmark_running = request.config.getoption("--codspeed", default=False)
    if marker is not None and not benchmark_running:
        pytest.skip("needs '--codspeed' to run")
