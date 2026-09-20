"""คำนวณพิกัดมาร์กเกอร์และ bubble จาก config

ใช้ร่วมกันทั้งตอนสร้างกระดาษ (PDF/PNG) และตอนอ่านภาพหลัง warp
พิกัดพิกเซลอ้างอิงภาพ WARP_WIDTH_PX × WARP_HEIGHT_PX ซึ่งเท่ากับหน้ากระดาษทั้งแผ่นที่ ~150 DPI
"""

from __future__ import annotations

import math

import numpy as np

from omr import config as C

# สเกล mm → px แยกแกน เพื่อให้หน้ากระดาษพอดีภาพปลายทางทุกพิกเซล
SX: float = C.WARP_WIDTH_PX / C.PAGE_WIDTH_MM
SY: float = C.WARP_HEIGHT_PX / C.PAGE_HEIGHT_MM
S_AVG: float = (SX + SY) / 2.0

Bubble = tuple[float, float, float]  # (x, y, r)


def mm_to_px(x_mm: float, y_mm: float) -> tuple[float, float]:
    """แปลงพิกัด mm เป็น px"""
    return x_mm * SX, y_mm * SY


# ---------------------------------------------------------------------------
# พิกัดหน่วย mm
# ---------------------------------------------------------------------------
def marker_boxes_mm() -> list[tuple[float, float, float, float]]:
    """กรอบมาร์กเกอร์ (x0, y0, x1, y1) เรียง TL, TR, BR, BL"""
    s, m = C.MARKER_SIZE_MM, C.MARKER_MARGIN_MM
    w, h = C.PAGE_WIDTH_MM, C.PAGE_HEIGHT_MM
    return [
        (m, m, m + s, m + s),
        (w - m - s, m, w - m, m + s),
        (w - m - s, h - m - s, w - m, h - m),
        (m, h - m - s, m + s, h - m),
    ]


def marker_centers_mm() -> np.ndarray:
    """จุดกึ่งกลางมาร์กเกอร์ (4,2) หน่วย mm เรียง TL, TR, BR, BL"""
    return np.array([((x0 + x1) / 2, (y0 + y1) / 2) for x0, y0, x1, y1 in marker_boxes_mm()])


def answer_columns(num_questions: int = C.NUM_QUESTIONS) -> int:
    """จำนวนคอลัมน์คำตอบ"""
    return max(1, math.ceil(num_questions / C.QUESTIONS_PER_COLUMN))


def answer_column_left_mm(col: int, num_questions: int = C.NUM_QUESTIONS) -> float:
    """ขอบซ้ายของคอลัมน์คำตอบ (เริ่มที่ช่องเลขข้อ)"""
    n_cols = answer_columns(num_questions)
    col_width = column_width_mm()
    region = C.ANSWER_REGION_RIGHT_MM - C.ANSWER_REGION_LEFT_MM
    if n_cols == 1:
        pitch = 0.0
    else:
        pitch = min(C.ANSWER_COL_PITCH_MAX_MM, (region - col_width) / (n_cols - 1))
    block_width = pitch * (n_cols - 1) + col_width
    start = C.ANSWER_REGION_LEFT_MM + (region - block_width) / 2
    return start + col * pitch


def column_width_mm() -> float:
    """ความกว้างของคอลัมน์คำตอบหนึ่งคอลัมน์ (เลขข้อ + bubble ทั้งหมด)"""
    return C.ANSWER_NUMBER_WIDTH_MM + C.BUBBLE_PITCH_X_MM * (len(C.CHOICES) - 1) + C.BUBBLE_DIAMETER_MM


def answer_bubbles_mm(num_questions: int = C.NUM_QUESTIONS) -> dict[int, dict[str, Bubble]]:
    """bubble คำตอบหน่วย mm: {ข้อ: {ตัวเลือก: (x, y, r)}}"""
    if not 1 <= num_questions <= C.MAX_QUESTIONS:
        raise ValueError(f"จำนวนข้อต้องอยู่ระหว่าง 1–{C.MAX_QUESTIONS}")
    r = C.BUBBLE_DIAMETER_MM / 2
    out: dict[int, dict[str, Bubble]] = {}
    for q in range(1, num_questions + 1):
        col, row = divmod(q - 1, C.QUESTIONS_PER_COLUMN)
        left = answer_column_left_mm(col, num_questions)
        y = C.ANSWER_FIRST_CENTER_Y_MM + row * C.BUBBLE_PITCH_Y_MM
        first_x = left + C.ANSWER_NUMBER_WIDTH_MM + r
        out[q] = {ch: (first_x + i * C.BUBBLE_PITCH_X_MM, y, r) for i, ch in enumerate(C.CHOICES)}
    return out


def student_id_bubbles_mm() -> list[dict[int, Bubble]]:
    """bubble รหัสนักศึกษาหน่วย mm: list ต่อหลัก ของ {เลข: (x, y, r)}"""
    r = C.BUBBLE_DIAMETER_MM / 2
    return [
        {
            d: (C.ID_FIRST_CENTER_X_MM + col * C.ID_PITCH_X_MM, C.ID_FIRST_CENTER_Y_MM + d * C.ID_PITCH_Y_MM, r)
            for d in C.DIGITS
        }
        for col in range(C.STUDENT_ID_DIGITS)
    ]


# ---------------------------------------------------------------------------
# พิกัดหน่วย px (ภาพหลัง warp)
# ---------------------------------------------------------------------------
def _to_px(b: Bubble) -> Bubble:
    x, y = mm_to_px(b[0], b[1])
    return (x, y, b[2] * S_AVG)


def marker_centers_px() -> np.ndarray:
    """จุดกึ่งกลางมาร์กเกอร์ (4,2) px เรียง TL, TR, BR, BL — ใช้เป็นปลายทาง warp"""
    mm = marker_centers_mm()
    return np.stack([mm[:, 0] * SX, mm[:, 1] * SY], axis=1).astype(np.float32)


def marker_size_px() -> float:
    """ขนาดด้านมาร์กเกอร์ (px)"""
    return C.MARKER_SIZE_MM * S_AVG


def marker_hole_px() -> float:
    """ขนาดช่องขาวในมาร์กเกอร์ TL (px)"""
    return C.MARKER_HOLE_MM * S_AVG


def answer_bubbles_px(num_questions: int = C.NUM_QUESTIONS) -> dict[int, dict[str, Bubble]]:
    """bubble คำตอบหน่วย px: {ข้อ: {ตัวเลือก: (x, y, r)}}"""
    return {q: {ch: _to_px(b) for ch, b in row.items()} for q, row in answer_bubbles_mm(num_questions).items()}


def student_id_bubbles_px() -> list[dict[int, Bubble]]:
    """bubble รหัสนักศึกษาหน่วย px: list ต่อหลัก"""
    return [{d: _to_px(b) for d, b in col.items()} for col in student_id_bubbles_mm()]


def student_id_frame_px() -> tuple[int, int, int, int]:
    """กรอบรอบบล็อกรหัสนักศึกษา (x0, y0, x1, y1) px"""
    cols = student_id_bubbles_mm()
    r = C.BUBBLE_DIAMETER_MM / 2
    pad = C.ID_FRAME_PAD_MM
    x0 = cols[0][0][0] - r - pad
    x1 = cols[-1][0][0] + r + pad
    y0 = C.ID_LABEL_Y_MM - pad
    y1 = cols[0][C.DIGITS[-1]][1] + r + pad / 2
    (px0, py0), (px1, py1) = mm_to_px(x0, y0), mm_to_px(x1, y1)
    return int(px0), int(py0), int(px1), int(py1)


def question_row_px(q: int, num_questions: int = C.NUM_QUESTIONS) -> tuple[int, int, int, int]:
    """กรอบแถวคำตอบของข้อ q (x0, y0, x1, y1) px ครอบ bubble A–D และครึ่งระยะห่างแถวบน/ล่าง"""
    row = answer_bubbles_px(num_questions)[q]
    xs = [b[0] for b in row.values()]
    _, y, r = next(iter(row.values()))
    half_pitch = C.BUBBLE_PITCH_Y_MM * SY / 2
    return int(min(xs) - 2 * r), int(y - half_pitch), int(max(xs) + 2 * r), int(y + half_pitch)


def answer_region_px(num_questions: int = C.NUM_QUESTIONS) -> tuple[int, int, int, int]:
    """กรอบพื้นที่คำตอบทั้งหมด (x0, y0, x1, y1) px — ใช้ครอปภาพก่อนส่งเข้า YOLOv8n"""
    x0, y0 = mm_to_px(C.ANSWER_REGION_LEFT_MM - C.MARKER_CLEARANCE_MM, C.ANSWER_SEPARATOR_Y_MM)
    rows = min(num_questions, C.QUESTIONS_PER_COLUMN)
    last_y = C.ANSWER_FIRST_CENTER_Y_MM + (rows - 1) * C.BUBBLE_PITCH_Y_MM
    x1, y1 = mm_to_px(C.ANSWER_REGION_RIGHT_MM + C.MARKER_CLEARANCE_MM, last_y + C.BUBBLE_PITCH_Y_MM)
    return int(x0), int(y0), int(np.ceil(x1)), int(np.ceil(y1))
