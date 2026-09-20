"""ทดสอบการหามาร์กเกอร์และการตรวจทิศ"""

from __future__ import annotations

import cv2
import numpy as np
import pytest

from conftest import place_on_background
from omr import layout as L
from omr import preprocess
from omr.errors import MarkerNotFoundError


def _expected_centers(homography: np.ndarray) -> np.ndarray:
    pts = L.marker_centers_px().reshape(-1, 1, 2)
    return cv2.perspectiveTransform(pts, homography).reshape(-1, 2)


@pytest.mark.parametrize("angle", [0, 10, -10, 15, -15])
def test_find_markers_rotated(blank_sheet: np.ndarray, angle: float) -> None:
    img, hmg = place_on_background(blank_sheet, angle)
    found = preprocess.find_markers(img)
    expected = _expected_centers(hmg)
    # จับคู่จุดที่ใกล้ที่สุด (ลำดับตามภาพ)
    for p in expected:
        assert np.min(np.linalg.norm(found - p, axis=1)) < 3.0


@pytest.mark.parametrize("angle", [0, 12, -12])
def test_upside_down_is_fixed(blank_sheet: np.ndarray, angle: float) -> None:
    img, _ = place_on_background(blank_sheet, angle, upside_down=True)
    warped, rotated = preprocess.fix_orientation(preprocess.warp(img, preprocess.find_markers(img)))
    assert rotated
    diff = cv2.absdiff(cv2.cvtColor(warped, cv2.COLOR_BGR2GRAY), cv2.cvtColor(blank_sheet, cv2.COLOR_BGR2GRAY))
    assert float(diff.mean()) < 12.0


def test_upright_not_rotated(blank_sheet: np.ndarray) -> None:
    img, _ = place_on_background(blank_sheet, 5)
    _, rotated = preprocess.fix_orientation(preprocess.warp(img, preprocess.find_markers(img)))
    assert not rotated


def test_no_paper_raises() -> None:
    rng = np.random.default_rng(0)
    noise = cv2.GaussianBlur(rng.integers(0, 255, (1200, 900, 3), dtype=np.uint8), (0, 0), 3)
    with pytest.raises(MarkerNotFoundError) as exc:
        preprocess.find_markers(noise)
    assert "มาร์กเกอร์" in str(exc.value)


def test_cropped_corner_raises(blank_sheet: np.ndarray) -> None:
    img, _ = place_on_background(blank_sheet, 0, scale=1.1)
    cropped = img[300:, :].copy()  # ตัดมาร์กเกอร์ด้านบนทิ้ง
    with pytest.raises(MarkerNotFoundError):
        preprocess.find_markers(cropped)
