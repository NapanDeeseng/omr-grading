"""ทดสอบ perspective warp: จุดกึ่งกลางมาร์กเกอร์หลัง warp คลาดไม่เกิน 3 px"""

from __future__ import annotations

import cv2
import numpy as np
import pytest

from conftest import place_on_background
from omr import config as C
from omr import layout as L
from omr import preprocess


def _keystone(img: np.ndarray, amount: float) -> np.ndarray:
    h, w = img.shape[:2]
    src = np.float32([[0, 0], [w, 0], [w, h], [0, h]])
    d = amount * w
    dst = np.float32([[d, 0], [w - d, 0], [w, h], [0, h]])
    return cv2.warpPerspective(img, cv2.getPerspectiveTransform(src, dst), (w, h), borderValue=(40, 60, 80))


def _marker_centers_in_warped(warped: np.ndarray) -> np.ndarray:
    """วัดจุดกึ่งกลางมาร์กเกอร์จริงในภาพหลัง warp ด้วย centroid ของบริเวณมืด"""
    gray = cv2.cvtColor(warped, cv2.COLOR_BGR2GRAY)
    size = int(L.marker_size_px())
    out = []
    for cx, cy in L.marker_centers_px():
        x0, y0 = int(cx) - size, int(cy) - size
        roi = gray[y0: y0 + 2 * size, x0: x0 + 2 * size]
        _, mask = cv2.threshold(roi, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        n, labels, stats, cents = cv2.connectedComponentsWithStats(mask)
        idx = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
        x, y, w, h = stats[idx, :4]
        out.append((x0 + x + w / 2, y0 + y + h / 2))  # ใช้กึ่งกลาง bbox (ไม่กระทบจากช่องขาว)
    return np.array(out)


@pytest.mark.parametrize("angle,keystone", [(0, 0.0), (8, 0.03), (-14, 0.02), (15, 0.0)])
def test_warp_marker_error(blank_sheet: np.ndarray, angle: float, keystone: float) -> None:
    img, _ = place_on_background(blank_sheet, angle)
    if keystone:
        img = _keystone(img, keystone)
    warped = preprocess.warp(img, preprocess.find_markers(img))
    assert warped.shape[:2] == (C.WARP_HEIGHT_PX, C.WARP_WIDTH_PX)
    err = np.linalg.norm(_marker_centers_in_warped(warped) - L.marker_centers_px(), axis=1)
    assert err.max() <= 3.0, f"คลาด {err}"
