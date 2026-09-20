"""dataclass ของผลลัพธ์การอ่านและการตรวจ"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

# สถานะการอ่านรายข้อ
STATUS_OK = "OK"
STATUS_FAINT = "FAINT"
STATUS_MULTI = "MULTI"
STATUS_BLANK = "BLANK"


@dataclass
class ProblemBox:
    """กรอบบริเวณที่มีปัญหาบนภาพหลัง warp (จาก YOLOv8n หรือการตรวจคุณภาพภาพ)"""

    kind: str                              # เช่น multi_mark, faint_mark, erasure, glare
    label: str                             # ชื่อภาษาไทย
    score: float                           # ความมั่นใจของตัวตรวจจับ 0–1
    box: tuple[int, int, int, int]         # (x0, y0, x1, y1) px
    source: str = "yolo"                   # yolo | quality
    questions: list[int] = field(default_factory=list)  # ข้อที่กรอบนี้ทับ


@dataclass
class ReadResult:
    """ผลอ่าน bubble หนึ่งกลุ่ม (หนึ่งข้อ หรือรหัสหนึ่งหลัก)"""

    answer: str
    status: str
    confidence: float
    uncertain: bool
    ratios: dict[str, float]


@dataclass
class QuestionResult:
    """ผลตรวจรายข้อ"""

    number: int
    answer: str
    key: str
    status: str
    is_correct: bool
    confidence: float
    uncertain: bool
    ratios: dict[str, float] = field(default_factory=dict)
    edited: bool = False
    problem: str = ""  # ปัญหาที่ YOLO/ตรวจคุณภาพพบในแถวนี้ (ว่าง = ไม่พบ)


@dataclass
class SheetResult:
    """ผลตรวจหนึ่งแผ่น"""

    filename: str
    student_id: str = ""
    id_valid: bool = False
    id_confidence: float = 0.0
    questions: list[QuestionResult] = field(default_factory=list)
    score: int = 0
    total: int = 0
    percent: float = 0.0
    avg_confidence: float = 0.0
    n_uncertain: int = 0
    n_blank: int = 0
    n_multi: int = 0
    rotated: bool = False
    processing_ms: float = 0.0
    annotated_image: np.ndarray | None = None
    error: str | None = None
    # ข้อมูลเสริมสำหรับแก้ไข/ตรวจใหม่บน dashboard โดยไม่ต้องประมวลผลภาพซ้ำ
    warped_image: np.ndarray | None = None
    original_preview: np.ndarray | None = None
    id_reads: list[ReadResult] = field(default_factory=list)
    answer_reads: dict[int, ReadResult] = field(default_factory=dict)
    reviewed: bool = False
    # ผลตรวจเสริม: คุณภาพภาพ + YOLOv8n
    warnings: list[str] = field(default_factory=list)
    problem_boxes: list[ProblemBox] = field(default_factory=list)
    used_paper_fallback: bool = False  # ใช้ขอบกระดาษแทนมาร์กเกอร์

    @property
    def problem_questions(self) -> dict[int, str]:
        """ข้อ → ชื่อปัญหา (รวมทุกกรอบที่ทับข้อนั้น)"""
        labels: dict[int, list[str]] = {}
        for b in self.problem_boxes:
            for q in b.questions:
                seen = labels.setdefault(q, [])
                if b.label not in seen:
                    seen.append(b.label)
        return {q: ", ".join(v) for q, v in labels.items()}

    @property
    def needs_review(self) -> bool:
        """แผ่นนี้ควรให้ผู้ตรวจดูซ้ำหรือไม่"""
        if self.error is not None:
            return False
        if self.reviewed:
            return False
        return (not self.id_valid) or self.n_uncertain > 0 or self.n_multi > 0 or self.used_paper_fallback

    @property
    def status_label(self) -> str:
        """สถานะภาษาไทยของแผ่น"""
        if self.error is not None:
            return "ผิดพลาด"
        if self.needs_review:
            return "ต้องตรวจสอบ"
        return "สำเร็จ"
