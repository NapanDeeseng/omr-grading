"""อ่าน bubble จากภาพขาวดำหลัง warp และคำนวณความมั่นใจ"""

from __future__ import annotations

import logging

import numpy as np

from omr import config as C
from omr import layout as L
from omr.models import STATUS_BLANK, STATUS_FAINT, STATUS_MULTI, STATUS_OK, ReadResult

log = logging.getLogger(__name__)

_MASK_CACHE: dict[tuple[int, float], np.ndarray] = {}


def _circle_mask(half: int, radius: float) -> np.ndarray:
    """mask วงกลมขนาด (2*half+1)² แคชไว้ตามขนาด"""
    key = (half, round(radius, 2))
    if key not in _MASK_CACHE:
        yy, xx = np.mgrid[-half: half + 1, -half: half + 1]
        _MASK_CACHE[key] = (xx * xx + yy * yy) <= radius * radius
    return _MASK_CACHE[key]


def fill_ratio(binary: np.ndarray, x: float, y: float, r: float, sample_ratio: float = C.BUBBLE_SAMPLE_RATIO) -> float:
    """สัดส่วนพิกเซลหมึกในวงกลมรัศมี r*sample_ratio (ใช้เฉพาะ bounding box)"""
    rr = r * sample_ratio
    half = int(np.ceil(rr))
    cx, cy = int(round(x)), int(round(y))
    h, w = binary.shape[:2]
    y0, y1, x0, x1 = cy - half, cy + half + 1, cx - half, cx + half + 1
    if y0 < 0 or x0 < 0 or y1 > h or x1 > w:
        return 0.0
    mask = _circle_mask(half, rr)
    patch = binary[y0:y1, x0:x1]
    return float(np.count_nonzero(patch[mask])) / float(mask.sum())


def read_group(ratios: dict[str, float], th: C.Thresholds | None = None) -> ReadResult:
    """ตัดสินคำตอบของหนึ่งกลุ่มจากสัดส่วนการฝนของแต่ละตัวเลือก"""
    th = th or C.Thresholds()
    ordered = sorted(ratios.items(), key=lambda kv: kv[1], reverse=True)
    r1 = ordered[0][1]
    r2 = ordered[1][1] if len(ordered) > 1 else 0.0
    filled = [k for k, v in ratios.items() if v >= th.fill]  # คงลำดับตัวเลือกเดิม (A→D)

    if not filled and r1 < th.faint:
        answer, status = "", STATUS_BLANK
    elif not filled:
        answer, status = ordered[0][0], STATUS_FAINT
    elif len(filled) >= 2:
        answer, status = "".join(filled), STATUS_MULTI
    else:
        answer, status = filled[0], STATUS_OK

    if status == STATUS_BLANK:
        confidence = float(np.clip((th.faint - r1) / th.faint, 0.0, 1.0)) if th.faint > 0 else 1.0
    else:
        confidence = float(np.clip((r1 - r2) / C.CONFIDENCE_SCALE, 0.0, 1.0))
    uncertain = status == STATUS_FAINT or confidence < th.confidence
    return ReadResult(answer, status, confidence, uncertain, {k: round(v, 4) for k, v in ratios.items()})


def answer_ratios(binary: np.ndarray, num_questions: int, th: C.Thresholds | None = None) -> dict[int, dict[str, float]]:
    """สัดส่วนการฝนของทุก bubble คำตอบ"""
    th = th or C.Thresholds()
    return {
        q: {ch: fill_ratio(binary, x, y, r, th.sample_ratio) for ch, (x, y, r) in row.items()}
        for q, row in L.answer_bubbles_px(num_questions).items()
    }


def id_ratios(binary: np.ndarray, th: C.Thresholds | None = None) -> list[dict[str, float]]:
    """สัดส่วนการฝนของ bubble รหัสนักศึกษา (key เป็นสตริงตัวเลข)"""
    th = th or C.Thresholds()
    return [
        {str(d): fill_ratio(binary, x, y, r, th.sample_ratio) for d, (x, y, r) in col.items()}
        for col in L.student_id_bubbles_px()
    ]


def read_answers(binary: np.ndarray, num_questions: int, th: C.Thresholds | None = None) -> dict[int, ReadResult]:
    """อ่านคำตอบทุกข้อ"""
    return {q: read_group(r, th) for q, r in answer_ratios(binary, num_questions, th).items()}


def combine_student_id(reads: list[ReadResult]) -> tuple[str, bool, float]:
    """รวมผลรายหลักเป็นรหัส ใช้ '?' แทนหลักที่อ่านไม่ได้ คืน (รหัส, valid, ความมั่นใจต่ำสุด)"""
    digits = [r.answer if r.status == STATUS_OK else "?" for r in reads]
    valid = bool(reads) and all(r.status == STATUS_OK for r in reads)
    conf = min((r.confidence for r in reads), default=0.0)
    return "".join(digits), valid, conf


def read_student_id(binary: np.ndarray, th: C.Thresholds | None = None) -> tuple[str, bool, float, list[ReadResult]]:
    """อ่านรหัสนักศึกษาทีละหลักด้วย logic เดียวกับคำตอบ"""
    reads = [read_group(r, th) for r in id_ratios(binary, th)]
    sid, valid, conf = combine_student_id(reads)
    return sid, valid, conf, reads
