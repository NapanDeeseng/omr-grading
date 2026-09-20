"""ตรวจคุณภาพภาพหลัง warp: เบลอ, มืดเกิน, แสงสะท้อน

- OpenCV: Laplacian variance (ความคม)
- scikit-image: label + regionprops หาบริเวณแสงสะท้อนเป็นกรอบ (bounding box)
"""

from __future__ import annotations

import cv2
import numpy as np
from skimage.measure import label, regionprops

from omr import config as C
from omr.models import ProblemBox
from omr.preprocess import to_gray


def sharpness(gray: np.ndarray) -> float:
    """ความคมของภาพ (variance ของ Laplacian) — ค่าต่ำ = เบลอ"""
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def glare_boxes(gray: np.ndarray) -> list[ProblemBox]:
    """บริเวณแสงสะท้อน: พิกเซลอิ่มตัวที่สว่างกว่ากระดาษส่วนใหญ่ชัดเจน รวมเป็นกลุ่มด้วย regionprops"""
    level = max(C.QUALITY_GLARE_LEVEL, int(np.median(gray)) + C.QUALITY_GLARE_MARGIN)
    if level > 255:
        return []
    regions = regionprops(label(gray >= level, connectivity=2))
    boxes = []
    for reg in regions:
        if reg.area < C.QUALITY_GLARE_MIN_AREA_PX:
            continue
        y0, x0, y1, x1 = reg.bbox
        boxes.append(ProblemBox("glare", "แสงสะท้อน", 1.0, (x0, y0, x1, y1), source="quality"))
    return boxes


def assess(warped: np.ndarray) -> tuple[list[str], list[ProblemBox]]:
    """คืน (ข้อความเตือนระดับภาพ, กรอบบริเวณที่มีปัญหา)"""
    gray = to_gray(warped)
    warnings: list[str] = []
    if sharpness(gray) < C.QUALITY_BLUR_MIN_VAR:
        warnings.append("ภาพเบลอ — ถือกล้องให้นิ่งและแตะโฟกัสที่กระดาษ")
    if np.percentile(gray, C.QUALITY_PAPER_PERCENTILE) < C.QUALITY_DARK_PAPER:
        warnings.append("ภาพมืดเกินไป — เพิ่มแสงสว่าง")
    boxes = glare_boxes(gray)
    if boxes:
        warnings.append(f"พบแสงสะท้อน {len(boxes)} บริเวณ — ข้อที่อยู่ในบริเวณนั้นถูกทำเครื่องหมายให้ตรวจสอบ")
    return warnings, boxes
