"""fixture ร่วมของชุดทดสอบ"""

from __future__ import annotations

import sys
from pathlib import Path

import cv2
import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from omr.sheet_generator import generate_png_image  # noqa: E402


@pytest.fixture(scope="session")
def blank_sheet() -> np.ndarray:
    """กระดาษคำตอบเปล่า 1240×1754"""
    return generate_png_image()


def place_on_background(sheet: np.ndarray, angle_deg: float, upside_down: bool = False,
                        canvas: tuple[int, int] = (1500, 2000), scale: float = 0.8) -> tuple[np.ndarray, np.ndarray]:
    """วางกระดาษบนพื้นสีเข้มแล้วหมุน คืน (ภาพ, homography จากกระดาษไปภาพ)"""
    h, w = sheet.shape[:2]
    cw, ch = canvas
    angle = angle_deg + (180.0 if upside_down else 0.0)
    rot = cv2.getRotationMatrix2D((w / 2, h / 2), angle, scale)
    rot[0, 2] += cw / 2 - w / 2
    rot[1, 2] += ch / 2 - h / 2
    img = cv2.warpAffine(sheet, rot, (cw, ch), borderValue=(40, 60, 80))
    homography = np.vstack([rot, [0, 0, 1]])
    return img, homography


def encode_jpg(img: np.ndarray) -> bytes:
    ok, enc = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 90])
    assert ok
    return enc.tobytes()
