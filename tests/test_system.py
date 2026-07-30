"""Environment detection logic.

The probes themselves shell out to real binaries, so these tests target the
decision logic layered on top — which is where a wrong answer would silently
cost users performance or produce a broken render.
"""

from __future__ import annotations

import pytest
from clipforge.system import REQUIRED_FILTERS, FFmpegInfo, GPUInfo


class TestComputeTypeSelection:
    @pytest.mark.parametrize(
        ("compute_capability", "expected"),
        [
            (6.1, "int8_float16"),  # GTX 1060 — Pascal, no fp16 tensor cores
            (6.0, "int8_float16"),  # Tesla P100
            (7.0, "float16"),  # Volta — first with fp16 tensor cores
            (7.5, "float16"),  # RTX 20-series
            (8.9, "float16"),  # RTX 40-series
            (12.0, "float16"),
        ],
    )
    def test_cuda_picks_by_compute_capability(
        self, compute_capability: float, expected: str
    ) -> None:
        gpu = GPUInfo(accel="cuda", compute_capability=compute_capability)

        assert gpu.compute_type == expected

    def test_unknown_compute_capability_assumes_fp16_is_fine(self) -> None:
        # Reporting no capability means an older driver; float16 is the safe
        # default because every CUDA device supports it, just not always fast.
        gpu = GPUInfo(accel="cuda", compute_capability=None)

        assert gpu.compute_type == "float16"

    def test_apple_silicon_uses_int8_on_cpu(self) -> None:
        gpu = GPUInfo(accel="mps")

        assert gpu.compute_type == "int8"
        # CTranslate2 has no Metal backend, so the device string must stay "cpu".
        assert gpu.device == "cpu"

    def test_cpu_uses_int8(self) -> None:
        gpu = GPUInfo(accel="cpu")

        assert gpu.compute_type == "int8"
        assert gpu.device == "cpu"

    def test_cuda_device_string(self) -> None:
        assert GPUInfo(accel="cuda").device == "cuda"


class TestFFmpegUsability:
    def _complete(self, **overrides) -> FFmpegInfo:
        defaults = {
            "found": True,
            "ffprobe_found": True,
            "has_libass": True,
            "has_libx264": True,
            "filters": set(REQUIRED_FILTERS),
        }
        return FFmpegInfo(**{**defaults, **overrides})

    def test_complete_build_is_usable(self) -> None:
        assert self._complete().usable is True

    def test_missing_filters_are_reported(self) -> None:
        info = self._complete(filters={"crop", "scale"})

        assert set(info.missing_filters) == {"ass", "concat", "loudnorm"}
        assert info.usable is False

    @pytest.mark.parametrize(
        "missing",
        ["found", "ffprobe_found", "has_libass", "has_libx264"],
    )
    def test_each_requirement_is_load_bearing(self, missing: str) -> None:
        assert self._complete(**{missing: False}).usable is False

    def test_nvenc_is_optional(self) -> None:
        # Software encode is a valid fallback, so a build without nvenc is fine.
        assert self._complete(has_nvenc=False).usable is True

    def test_not_found_reports_all_filters_missing(self) -> None:
        info = FFmpegInfo()

        assert set(info.missing_filters) == set(REQUIRED_FILTERS)
        assert info.usable is False
