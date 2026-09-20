"""ขั้นเตรียมภาพ: หามาร์กเกอร์ 4 มุม (หรือขอบกระดาษ), perspective warp, ตรวจทิศกระดาษ, threshold

- OpenCV: หามาร์กเกอร์/ขอบกระดาษ, warp
- imutils: grab_contours และ four_point_transform สำหรับกรณีใช้ขอบกระดาษ
- SciPy (ndimage): ลด noise ก่อน threshold และลบจุดหมึกโดดหลัง threshold
- scikit-image: adaptive (local) threshold
"""

from __future__ import annotations

import itertools
import logging
from dataclasses import dataclass
from pathlib import Path

import cv2
import imutils
import numpy as np
from imutils.perspective import four_point_transform
from scipy import ndimage
from skimage.filters import threshold_local

from omr import config as C
from omr import layout as L
from omr.errors import MarkerNotFoundError, PaperNotFoundError

log = logging.getLogger(__name__)


@dataclass
class _Candidate:
    center: np.ndarray  # (2,) พิกัดในภาพย่อ
    area: float
    contrast: float
    corners: np.ndarray  # (4,2)


def save_debug(debug_dir: Path | None, name: str, image: np.ndarray) -> None:
    """บันทึกภาพระหว่างขั้นตอนเมื่อเปิด debug"""
    if debug_dir is None:
        return
    debug_dir.mkdir(parents=True, exist_ok=True)
    ok, enc = cv2.imencode(".png", image)
    if ok:
        (debug_dir / name).write_bytes(enc.tobytes())


def to_gray(image: np.ndarray) -> np.ndarray:
    """แปลงเป็น grayscale ถ้ายังไม่เป็น"""
    if image.ndim == 2:
        return image
    return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)


def order_points(pts: np.ndarray) -> np.ndarray:
    """เรียงจุด 4 จุดเป็น TL, TR, BR, BL ด้วย sum/diff ของพิกัด"""
    pts = np.asarray(pts, dtype=np.float32).reshape(4, 2)
    s = pts.sum(axis=1)
    d = np.diff(pts, axis=1).ravel()  # y - x
    return np.array([pts[np.argmin(s)], pts[np.argmin(d)], pts[np.argmax(s)], pts[np.argmax(d)]], dtype=np.float32)


def _quad_center(corners: np.ndarray) -> np.ndarray:
    """จุดตัดเส้นทแยงมุม = จุดกึ่งกลางที่แท้จริงของสี่เหลี่ยมภายใต้ perspective"""
    p1, p2, p3, p4 = corners  # TL, TR, BR, BL
    d1, d2 = p3 - p1, p4 - p2
    denom = d1[0] * d2[1] - d1[1] * d2[0]
    if abs(denom) < 1e-9:
        return corners.mean(axis=0)
    t = ((p2[0] - p1[0]) * d2[1] - (p2[1] - p1[1]) * d2[0]) / denom
    return p1 + t * d1


def _is_convex(pts: np.ndarray) -> bool:
    """ตรวจว่า 4 จุดเรียงตามลำดับแล้วเป็นรูปนูน"""
    signs = []
    for i in range(4):
        a, b, c = pts[i], pts[(i + 1) % 4], pts[(i + 2) % 4]
        signs.append(np.sign((b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0])))
    return all(s > 0 for s in signs) or all(s < 0 for s in signs)


def _find_candidates(gray_small: np.ndarray, binary: np.ndarray) -> list[_Candidate]:
    """คัดรูปทรงที่มีลักษณะเป็นสี่เหลี่ยมทึบสีเข้ม"""
    h, w = gray_small.shape
    long_side = max(h, w)
    min_area = (C.MARKER_MIN_SIDE_FRAC * long_side) ** 2
    max_area = (C.MARKER_MAX_SIDE_FRAC * long_side) ** 2
    contours, _ = cv2.findContours(binary, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)

    cands: list[_Candidate] = []
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if not min_area <= area <= max_area:
            continue
        approx = cv2.approxPolyDP(cnt, C.DETECT_APPROX_EPS * cv2.arcLength(cnt, True), True)
        if len(approx) != 4 or not cv2.isContourConvex(approx):
            continue
        (_, (rw, rh), _) = cv2.minAreaRect(cnt)
        if rw <= 0 or rh <= 0:
            continue
        aspect = rw / rh
        if not C.MARKER_ASPECT_MIN <= aspect <= C.MARKER_ASPECT_MAX:
            continue
        if area / (rw * rh) < C.MARKER_MIN_EXTENT:
            continue
        hull_area = cv2.contourArea(cv2.convexHull(cnt))
        if hull_area <= 0 or area / hull_area < C.MARKER_MIN_SOLIDITY:
            continue

        # ความเข้มภายในเทียบกับวงรอบนอก (กันกรอบกลวงและพื้นผิวลายไม้)
        x, y, bw, bh = cv2.boundingRect(cnt)
        pad = max(bw, bh) // 2
        x0, y0 = max(0, x - pad), max(0, y - pad)
        x1, y1 = min(w, x + bw + pad), min(h, y + bh + pad)
        roi = gray_small[y0:y1, x0:x1]
        inner = np.zeros(roi.shape, np.uint8)
        cv2.drawContours(inner, [cnt - [x0, y0]], -1, 255, -1)
        outer = cv2.dilate(inner, np.ones((pad, pad), np.uint8)) if pad > 0 else inner
        ring = (outer > 0) & (inner == 0)
        if not ring.any():
            continue
        inside_mean = float(roi[inner > 0].mean())
        ring_mean = float(roi[ring].mean())
        if ring_mean <= 0 or inside_mean > ring_mean * C.MARKER_MAX_INSIDE_TO_RING:
            continue
        corners = order_points(approx.reshape(4, 2))
        cands.append(_Candidate(_quad_center(corners), area, ring_mean - inside_mean, corners))

    # ตัดตัวซ้ำ (เช่น contour ด้านในของมาร์กเกอร์) เก็บตัวที่ใหญ่กว่า
    cands.sort(key=lambda c: -c.area)
    unique: list[_Candidate] = []
    for c in cands:
        if all(np.linalg.norm(c.center - u.center) > np.sqrt(u.area) / 2 for u in unique):
            unique.append(c)
    unique.sort(key=lambda c: -c.contrast)
    return unique[: C.MARKER_MAX_CANDIDATES]


def _best_quad(cands: list[_Candidate]) -> list[_Candidate] | None:
    """เลือก 4 ตัวที่สอดคล้องกับรูปแบบมาร์กเกอร์มากที่สุด (กรอบใหญ่สุดที่ผ่านเงื่อนไข)"""
    best: list[_Candidate] | None = None
    best_area = -1.0
    for combo in itertools.combinations(cands, 4):
        areas = [c.area for c in combo]
        if max(areas) / min(areas) > C.MARKER_MAX_AREA_RATIO:
            continue
        pts = order_points(np.array([c.center for c in combo]))
        if len({tuple(p) for p in pts}) != 4 or not _is_convex(pts):
            continue
        top, right = np.linalg.norm(pts[1] - pts[0]), np.linalg.norm(pts[2] - pts[1])
        bottom, left = np.linalg.norm(pts[2] - pts[3]), np.linalg.norm(pts[3] - pts[0])
        width, height = (top + bottom) / 2, (left + right) / 2
        if min(width, height) <= 0:
            continue
        aspect = min(width, height) / max(width, height)
        if not C.QUAD_ASPECT_MIN <= aspect <= C.QUAD_ASPECT_MAX:
            continue
        side = float(np.sqrt(np.mean(areas)))
        if not C.MARKER_TO_SPAN_MIN <= side / max(width, height) <= C.MARKER_TO_SPAN_MAX:
            continue
        quad_area = float(cv2.contourArea(pts))
        if quad_area > best_area:
            best_area, best = quad_area, list(combo)
    return best


def find_markers(image: np.ndarray, debug_dir: Path | None = None) -> np.ndarray:
    """หาจุดกึ่งกลางมาร์กเกอร์ 4 มุม คืนค่า (4,2) พิกัดภาพต้นฉบับ เรียง TL, TR, BR, BL

    ลำดับอ้างอิงตามภาพ (ถ้ากระดาษกลับหัว fix_orientation จะแก้ภายหลัง)
    """
    h, w = image.shape[:2]
    scale = C.DETECT_LONG_SIDE_PX / max(h, w)
    small = cv2.resize(image, (round(w * scale), round(h * scale)), interpolation=cv2.INTER_AREA)
    gray = to_gray(small)
    blur = cv2.GaussianBlur(gray, (C.DETECT_BLUR_KSIZE, C.DETECT_BLUR_KSIZE), 0)
    binary = cv2.adaptiveThreshold(
        blur, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, C.DETECT_ADAPTIVE_BLOCK, C.DETECT_ADAPTIVE_C
    )
    kernel = np.ones((C.DETECT_CLOSE_KSIZE, C.DETECT_CLOSE_KSIZE), np.uint8)
    binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
    save_debug(debug_dir, "01_original.png", small)
    save_debug(debug_dir, "02_detect_threshold.png", binary)

    cands = _find_candidates(gray, binary)
    chosen = _best_quad(cands) if len(cands) >= 4 else None

    if debug_dir is not None:
        vis = small.copy() if small.ndim == 3 else cv2.cvtColor(small, cv2.COLOR_GRAY2BGR)
        for c in cands:
            cv2.polylines(vis, [c.corners.astype(np.int32)], True, C.COLOR_UNCERTAIN, 2)
        for c in chosen or []:
            cv2.polylines(vis, [c.corners.astype(np.int32)], True, C.COLOR_CORRECT, 3)
        save_debug(debug_dir, "03_markers.png", vis)

    if chosen is None:
        raise MarkerNotFoundError(min(len(cands), 3))

    pts = order_points(np.array([c.center for c in chosen]))
    # ถ้ากรอบกว้างกว่าสูง (ภาพแนวนอน/หมุน 90°) ให้เลื่อนลำดับจุด; ทิศ 180° แก้ใน fix_orientation
    width = np.linalg.norm(pts[1] - pts[0])
    height = np.linalg.norm(pts[3] - pts[0])
    if width > height:
        pts = np.roll(pts, 1, axis=0)
    return (pts / scale).astype(np.float32)


def warp(image: np.ndarray, markers: np.ndarray) -> np.ndarray:
    """perspective transform ให้จุดกึ่งกลางมาร์กเกอร์ไปอยู่ตำแหน่งตามแบบ ได้ภาพ 1240×1754"""
    matrix = cv2.getPerspectiveTransform(np.asarray(markers, np.float32), L.marker_centers_px())
    return cv2.warpPerspective(
        image, matrix, (C.WARP_WIDTH_PX, C.WARP_HEIGHT_PX), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE
    )


def find_paper(image: np.ndarray, debug_dir: Path | None = None) -> np.ndarray:
    """หามุมกระดาษ 4 มุมจากขอบ (Canny + contour) คืน (4,2) พิกัดภาพต้นฉบับ เรียง TL, TR, BR, BL

    ใช้สำรองเมื่อหามาร์กเกอร์ไม่ครบ (เช่น มุมหนึ่งโดนนิ้วบัง) — แม่นยำน้อยกว่ามาร์กเกอร์
    เพราะเครื่องพิมพ์อาจเลื่อน/ย่อหน้ากระดาษเล็กน้อย
    """
    h, w = image.shape[:2]
    small = imutils.resize(image, height=C.DETECT_LONG_SIDE_PX) if h >= w else imutils.resize(
        image, width=C.DETECT_LONG_SIDE_PX)
    scale = small.shape[0] / h
    gray = cv2.GaussianBlur(to_gray(small), (C.DETECT_BLUR_KSIZE, C.DETECT_BLUR_KSIZE), 0)
    edges = cv2.Canny(gray, C.PAPER_CANNY_LOW, C.PAPER_CANNY_HIGH)
    edges = cv2.dilate(edges, np.ones((C.PAPER_DILATE_PX, C.PAPER_DILATE_PX), np.uint8))
    save_debug(debug_dir, "02b_paper_edges.png", edges)

    contours = imutils.grab_contours(cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE))
    img_area = small.shape[0] * small.shape[1]
    for cnt in sorted(contours, key=cv2.contourArea, reverse=True)[:5]:
        area = cv2.contourArea(cnt)
        if area < C.PAPER_MIN_AREA_FRAC * img_area:
            break
        if area > C.PAPER_MAX_AREA_FRAC * img_area:  # กรอบภาพเอง ไม่ใช่กระดาษ
            continue
        approx = cv2.approxPolyDP(cnt, C.DETECT_APPROX_EPS * cv2.arcLength(cnt, True), True)
        if len(approx) != 4 or not cv2.isContourConvex(approx):
            continue
        pts = order_points(approx.reshape(4, 2))
        width = (np.linalg.norm(pts[1] - pts[0]) + np.linalg.norm(pts[2] - pts[3])) / 2
        height = (np.linalg.norm(pts[3] - pts[0]) + np.linalg.norm(pts[2] - pts[1])) / 2
        if width > height:  # ภาพแนวนอน: ให้ด้านยาวเป็นแนวตั้ง
            pts = np.roll(pts, 1, axis=0)
            width, height = height, width
        if not C.PAPER_ASPECT_MIN <= width / height <= C.PAPER_ASPECT_MAX:
            continue
        return (pts / scale).astype(np.float32)
    raise PaperNotFoundError()


def warp_paper(image: np.ndarray, corners: np.ndarray) -> np.ndarray:
    """ตัดและปรับระนาบกระดาษด้วย imutils.four_point_transform แล้วย่อ/ขยายเป็นขนาดมาตรฐาน 1240×1754

    four_point_transform เรียงจุดใหม่ตามพิกัด จึงหมุนภาพให้ด้านยาวเป็นแนวตั้งภายหลัง
    """
    flat = four_point_transform(image, np.asarray(corners, np.float32))
    if flat.shape[1] > flat.shape[0]:
        flat = cv2.rotate(flat, cv2.ROTATE_90_CLOCKWISE)
    return cv2.resize(flat, (C.WARP_WIDTH_PX, C.WARP_HEIGHT_PX), interpolation=cv2.INTER_LINEAR)


def _patch_mean(gray: np.ndarray, center: np.ndarray, half: int) -> float:
    x, y = int(round(center[0])), int(round(center[1]))
    patch = gray[max(0, y - half): y + half + 1, max(0, x - half): x + half + 1]
    return float(patch.mean()) if patch.size else 0.0


def fix_orientation(warped: np.ndarray) -> tuple[np.ndarray, bool]:
    """ตรวจช่องขาวในมาร์กเกอร์ TL ถ้าไปอยู่ที่ BR แสดงว่ากลับหัว ให้หมุน 180°"""
    gray = to_gray(warped)
    centers = L.marker_centers_px()
    half = max(1, int(L.marker_hole_px() * C.ORIENT_SAMPLE_FRAC / 2))
    tl = _patch_mean(gray, centers[0], half)
    br = _patch_mean(gray, centers[2], half)
    if br - tl > C.ORIENT_MIN_DIFF:
        return cv2.rotate(warped, cv2.ROTATE_180), True
    if tl - br <= C.ORIENT_MIN_DIFF:
        log.warning("ตรวจทิศกระดาษไม่ชัดเจน (TL=%.0f, BR=%.0f) ถือว่าไม่กลับหัว", tl, br)
    return warped, False


def normalize_lighting(warped: np.ndarray) -> np.ndarray:
    """ลบเงาด้วยการหารพื้นหลัง (morphological close ของ OpenCV) คืนภาพเทา uint8"""
    gray = to_gray(warped)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (C.BG_KERNEL_PX, C.BG_KERNEL_PX))
    background = cv2.morphologyEx(gray, cv2.MORPH_CLOSE, kernel)
    return cv2.divide(gray, background, scale=C.NORMALIZE_MAX)


def binarize(warped: np.ndarray, debug_dir: Path | None = None) -> np.ndarray:
    """ลบเงา → ลด noise (SciPy) → adaptive threshold (scikit-image) → ลบจุดโดด (SciPy) คืนภาพหมึก = 255"""
    normalized = normalize_lighting(warped)
    smooth = normalized.astype(np.float32)
    if C.DENOISE_SIGMA > 0:
        smooth = ndimage.gaussian_filter(smooth, C.DENOISE_SIGMA)
    # threshold_local แบบ mean: หมึกคือพิกเซลที่มืดกว่าค่าเฉลี่ยรอบข้างเกิน offset (เทียบเท่า ADAPTIVE_THRESH_MEAN_C)
    local = threshold_local(smooth, C.BIN_ADAPTIVE_BLOCK, method="mean", offset=C.BIN_ADAPTIVE_C, mode="nearest")
    ink = smooth <= local
    if C.SPECKLE_OPEN_PX > 1:
        ink = ndimage.binary_opening(ink, structure=np.ones((C.SPECKLE_OPEN_PX, C.SPECKLE_OPEN_PX), bool))
    binary = ink.astype(np.uint8) * 255
    save_debug(debug_dir, "05_normalized.png", normalized)
    save_debug(debug_dir, "06_binary.png", binary)
    return binary
