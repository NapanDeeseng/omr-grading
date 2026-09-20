"""YOLOv8n: ตรวจจับกรอบบริเวณที่มีปัญหาบนกระดาษคำตอบ (ฝนหลายตัวเลือก / ฝนจาง / รอยลบ)

ทำงานบนพื้นที่คำตอบที่ครอปจากภาพหลัง warp แล้วผูกแต่ละกรอบกับข้อที่ทับ
ข้อที่ถูกผูกจะถูกทำเครื่องหมาย "ไม่มั่นใจ" ให้ผู้ตรวจดู — YOLO ไม่เปลี่ยนคำตอบที่อ่านได้
(การอ่านคำตอบยังใช้ fill ratio ซึ่งแม่นกว่า YOLO เป็นความเห็นที่สอง)

ไม่บังคับ: ถ้ายังไม่ได้ติดตั้ง ultralytics หรือยังไม่มีไฟล์โมเดล ระบบข้ามขั้นนี้
สร้างโมเดลด้วย: python tools/train_yolo.py
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Any

import numpy as np

from omr import config as C
from omr import layout as L
from omr.models import ProblemBox

log = logging.getLogger(__name__)

_model: Any = None
_model_path: Path | None = None
_status: str = "ยังไม่ได้โหลด"
# กันโหลดซ้อนกัน: preload() ในเธรดพื้นหลังกับ detect() ตอนเริ่มตรวจอาจเรียกพร้อมกัน
_lock = threading.Lock()
_preload: threading.Thread | None = None


def status() -> str:
    """ข้อความสถานะของตัวตรวจจับ (แสดงบน dashboard)"""
    return _status


def load_model(weights: Path = C.YOLO_WEIGHTS) -> Any:
    """โหลดโมเดล YOLOv8n ครั้งเดียว คืน None ถ้าใช้ไม่ได้"""
    with _lock:
        return _load(weights)


def _load(weights: Path) -> Any:
    global _model, _model_path, _status
    if _model is not None and _model_path == weights:
        return _model
    if not weights.is_file():
        _status = f"ไม่พบไฟล์โมเดล {weights.name} — สร้างด้วย python tools/train_yolo.py"
        return None
    try:
        from ultralytics import YOLO
    except ImportError:
        _status = "ยังไม่ได้ติดตั้ง ultralytics (pip install ultralytics)"
        return None
    try:
        _model, _model_path = YOLO(str(weights)), weights
    except Exception as exc:  # noqa: BLE001 — ไฟล์โมเดลเสียต้องไม่ทำให้ระบบล่ม
        _status = f"โหลดโมเดลไม่สำเร็จ: {exc}"
        log.warning(_status)
        return None
    _status = f"พร้อมใช้งาน ({weights.name})"
    return _model


def preload() -> None:
    """เริ่มโหลดโมเดลในเธรดพื้นหลัง (import torch ใช้หลายวินาที) หน้าเว็บจึงแสดงได้ทันที
    ไม่ทำอะไรถ้าโหลดแล้วหรือกำลังโหลดอยู่ — ถ้ายังไม่มีไฟล์โมเดล เรียกใหม่ครั้งหน้าจะตรวจไฟล์อีกรอบ"""
    global _preload, _status
    if _model is not None or (_preload is not None and _preload.is_alive()):
        return
    if _status == "ยังไม่ได้โหลด":
        _status = "กำลังโหลดโมเดล…"
    _preload = threading.Thread(target=load_model, name="yolo-preload", daemon=True)
    _preload.start()


def assign_questions(boxes: list[ProblemBox], num_questions: int = C.NUM_QUESTIONS) -> list[ProblemBox]:
    """ผูกกรอบปัญหากับข้อที่ทับ (ทับ ≥ YOLO_ROW_MIN_OVERLAP ของกรอบที่เล็กกว่า)"""
    rows = {q: L.question_row_px(q, num_questions) for q in range(1, num_questions + 1)}
    for b in boxes:
        bx0, by0, bx1, by1 = b.box
        b_area = max(1, (bx1 - bx0) * (by1 - by0))
        b.questions = []
        for q, (rx0, ry0, rx1, ry1) in rows.items():
            iw = min(bx1, rx1) - max(bx0, rx0)
            ih = min(by1, ry1) - max(by0, ry0)
            if iw <= 0 or ih <= 0:
                continue
            smaller = min(b_area, (rx1 - rx0) * (ry1 - ry0))
            if iw * ih / smaller >= C.YOLO_ROW_MIN_OVERLAP:
                b.questions.append(q)
    return boxes


def detect(warped: np.ndarray, num_questions: int = C.NUM_QUESTIONS) -> list[ProblemBox]:
    """ตรวจจับกรอบปัญหาในพื้นที่คำตอบ คืนพิกัดในภาพหลัง warp (ว่างถ้าไม่มีโมเดล)"""
    model = load_model()
    if model is None:
        return []
    x0, y0, x1, y1 = L.answer_region_px(num_questions)
    crop = warped[y0:y1, x0:x1]
    if crop.ndim == 2:
        crop = np.repeat(crop[..., None], 3, axis=2)
    try:
        pred = model.predict(crop, imgsz=C.YOLO_IMGSZ, conf=C.YOLO_CONF, verbose=False)[0]
    except Exception:  # noqa: BLE001 — YOLO เป็นความเห็นเสริม ล้มเหลวแล้วยังต้องตรวจแผ่นนี้ต่อได้
        log.exception("YOLOv8n ทำงานผิดพลาด ข้ามการตรวจจับบริเวณที่มีปัญหา")
        return []
    boxes: list[ProblemBox] = []
    names = pred.names
    for xyxy, cls, score in zip(pred.boxes.xyxy.cpu().numpy(), pred.boxes.cls.cpu().numpy(),
                                pred.boxes.conf.cpu().numpy()):
        kind = names[int(cls)]
        bx0, by0, bx1, by1 = (int(round(v)) for v in xyxy)
        boxes.append(ProblemBox(kind, C.YOLO_CLASS_TH.get(kind, kind), round(float(score), 3),
                                (bx0 + x0, by0 + y0, bx1 + x0, by1 + y0)))
    return assign_questions(boxes, num_questions)
