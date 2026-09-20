"""วาดผลการตรวจลงภาพหลัง warp (ข้อความอังกฤษ/ตัวเลขเท่านั้น)"""

from __future__ import annotations

import math

import cv2
import numpy as np

from omr import config as C
from omr import layout as L
from omr.models import STATUS_BLANK, STATUS_MULTI, SheetResult


def _pt(x: float, y: float) -> tuple[int, int]:
    return int(round(x)), int(round(y))


def _dashed_circle(img: np.ndarray, x: float, y: float, r: float, color: tuple[int, int, int], thick: int) -> None:
    """วงกลมเส้นประ (วาดเป็นส่วนโค้งสลับ)"""
    step = 360.0 / (C.ANNOTATE_DASH_SEGMENTS * 2)
    for i in range(C.ANNOTATE_DASH_SEGMENTS):
        start = i * 2 * step
        cv2.ellipse(img, _pt(x, y), (int(r), int(r)), 0, start, start + step, color, thick, cv2.LINE_AA)


def annotate(warped: np.ndarray, sheet: SheetResult) -> np.ndarray:
    """คืนภาพสีที่วาดผลตรวจแล้ว"""
    img = warped.copy() if warped.ndim == 3 else cv2.cvtColor(warped, cv2.COLOR_GRAY2BGR)
    num_q = max((q.number for q in sheet.questions), default=C.NUM_QUESTIONS)
    bubbles = L.answer_bubbles_px(max(num_q, 1))
    extra = C.ANNOTATE_RING_EXTRA_PX

    for q in sheet.questions:
        row = bubbles.get(q.number)
        if row is None:
            continue
        if q.status in (STATUS_MULTI, STATUS_BLANK):
            # กรอบส้มรอบทั้งแถว
            xs = [b[0] for b in row.values()]
            y, r = next(iter(row.values()))[1:]
            pad = C.ANNOTATE_ROW_PAD_PX
            cv2.rectangle(img, _pt(min(xs) - r - pad, y - r - pad), _pt(max(xs) + r + pad, y + r + pad),
                          C.COLOR_ROW_ALERT, C.ANNOTATE_THICK)
        for ch in q.answer:
            if ch not in row:
                continue
            x, y, r = row[ch]
            if q.uncertain:
                color = C.COLOR_UNCERTAIN
            elif q.is_correct:
                color = C.COLOR_CORRECT
            else:
                color = C.COLOR_WRONG
            cv2.circle(img, _pt(x, y), int(r + extra), color, C.ANNOTATE_THICK, cv2.LINE_AA)
        if not q.is_correct and q.key in row:
            x, y, r = row[q.key]
            _dashed_circle(img, x, y, r + extra, C.COLOR_CORRECT, C.ANNOTATE_THICK - 1)

    # กรอบปัญหาจาก YOLOv8n (ม่วง) และแสงสะท้อน (ฟ้า) — ข้อความอังกฤษเพราะ OpenCV วาดไทยไม่ได้
    for b in sheet.problem_boxes:
        color = C.COLOR_GLARE if b.source == "quality" else C.COLOR_AI_BOX
        cv2.rectangle(img, b.box[:2], b.box[2:], color, C.ANNOTATE_THICK - 1)
        tag = b.kind if b.source == "quality" else f"{b.kind} {b.score:.2f}"
        cv2.putText(img, tag, (b.box[0], max(12, b.box[1] - 4)), cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1,
                    cv2.LINE_AA)

    # รหัสนักศึกษา
    x0, y0, x1, y1 = L.student_id_frame_px()
    id_color = C.COLOR_CORRECT if sheet.id_valid else C.COLOR_WRONG
    cv2.rectangle(img, (x0, y0), (x1, y1), id_color, C.ANNOTATE_THICK)
    for col, read in zip(L.student_id_bubbles_px(), sheet.id_reads):
        for ch in read.answer:
            if ch.isdigit() and int(ch) in col:
                x, y, r = col[int(ch)]
                cv2.circle(img, _pt(x, y), int(r + extra), id_color, C.ANNOTATE_THICK - 1, cv2.LINE_AA)

    # คะแนนมุมบน
    text = f"{sheet.score}/{sheet.total}"
    org = C.ANNOTATE_SCORE_POS_PX
    cv2.putText(img, text, org, cv2.FONT_HERSHEY_SIMPLEX, C.ANNOTATE_FONT_SCALE, (255, 255, 255),
                C.ANNOTATE_FONT_THICK * 3, cv2.LINE_AA)
    cv2.putText(img, text, org, cv2.FONT_HERSHEY_SIMPLEX, C.ANNOTATE_FONT_SCALE, C.COLOR_TEXT,
                C.ANNOTATE_FONT_THICK, cv2.LINE_AA)
    sid = f"ID {sheet.student_id}" + ("" if sheet.id_valid else " (?)")
    sid_org = (org[0], org[1] + int(math.ceil(C.ANNOTATE_FONT_SCALE * 30)))
    cv2.putText(img, sid, sid_org, cv2.FONT_HERSHEY_SIMPLEX, C.ANNOTATE_FONT_SCALE * 0.6, id_color,
                max(1, C.ANNOTATE_FONT_THICK // 2), cv2.LINE_AA)
    return img
