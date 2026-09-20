"""สร้างกระดาษคำตอบ: PDF สำหรับพิมพ์ และ PNG สำหรับสร้างภาพทดสอบ

ทั้งสองไฟล์วาดผ่าน "backend" ที่มีเมธอดเดียวกัน โดยอ่านพิกัดจาก layout.py ชุดเดียว
จึงรับประกันว่าพิกัดตรงกัน
"""

from __future__ import annotations

import io
import logging
import os
from pathlib import Path
from typing import Protocol

import cv2
import numpy as np

from omr import config as C
from omr import layout as L

log = logging.getLogger(__name__)

# ชื่อไฟล์ฟอนต์ไทยที่ลองหา (ถ้าไม่พบใช้ข้อความอังกฤษ)
THAI_FONT_FILES: tuple[str, ...] = ("Sarabun-Regular.ttf", "THSarabunNew.ttf", "THSarabun.ttf")

TEXT_EN: dict[str, str] = {
    "title": "OMR ANSWER SHEET",
    "subtitle": "Automated Multiple-Choice Exam Grading",
    "name": "Name",
    "subject": "Subject",
    "date": "Date",
    "section": "Section",
    "instr_head": "INSTRUCTIONS",
    "instr1": "1. Use a dark pencil (2B) or black pen. Fill the circle completely.",
    "instr2": "2. Fill only ONE choice per question. Erase changes cleanly.",
    "instr3": "3. Write your student ID in the boxes and fill the digits below.",
    "instr4": "4. Do not fold, staple or mark the four black corner squares.",
    "correct": "Correct:",
    "wrong": "Wrong:",
    "id": "STUDENT ID",
    "footer": "Photograph the whole sheet so all 4 corner markers are visible.",
}

TEXT_TH: dict[str, str] = {
    **TEXT_EN,
    "title": "กระดาษคำตอบ OMR",
    "subtitle": "ระบบตรวจข้อสอบปรนัยอัตโนมัติ",
    "name": "ชื่อ-สกุล",
    "subject": "วิชา",
    "date": "วันที่",
    "section": "กลุ่มเรียน",
    "instr_head": "คำแนะนำ",
    "instr1": "1. ใช้ดินสอ 2B หรือปากกาสีดำ ฝนให้เต็มวง",
    "instr2": "2. ฝนเพียงหนึ่งตัวเลือกต่อข้อ หากแก้ไขให้ลบให้สะอาด",
    "instr3": "3. เขียนรหัสนักศึกษาในช่อง และฝนตัวเลขด้านล่างให้ตรงกัน",
    "instr4": "4. ห้ามพับ เย็บ หรือขีดเขียนทับสี่เหลี่ยมดำทั้ง 4 มุม",
    "correct": "ถูกต้อง:",
    "wrong": "ไม่ถูกต้อง:",
    "id": "รหัสนักศึกษา",
    "footer": "ถ่ายภาพให้เห็นสี่เหลี่ยมดำครบทั้ง 4 มุม",
}


class Backend(Protocol):
    """อินเทอร์เฟซวาดรูปหน่วย mm (origin มุมบนซ้าย)"""

    def rect(self, x0: float, y0: float, x1: float, y1: float, fill: bool, gray: int = 0, lw: float = 0.3) -> None: ...
    def circle(self, x: float, y: float, r: float, fill: bool, gray: int = 0, lw: float = 0.3) -> None: ...
    def line(self, x0: float, y0: float, x1: float, y1: float, gray: int = 0, lw: float = 0.3) -> None: ...
    def text(self, x: float, y: float, s: str, pt: float, align: str = "left", gray: int = 0, bold: bool = False) -> None: ...


class PdfBackend:
    """วาดลง reportlab canvas"""

    def __init__(self, buf: io.BytesIO, thai_font: Path | None) -> None:
        from reportlab.lib.units import mm
        from reportlab.pdfgen import canvas

        self._mm = mm
        self.c = canvas.Canvas(buf, pagesize=(C.PAGE_WIDTH_MM * mm, C.PAGE_HEIGHT_MM * mm))
        self.font, self.font_bold = "Helvetica", "Helvetica-Bold"
        self.thai_font: str | None = None
        if thai_font is not None:
            from reportlab.pdfbase import pdfmetrics
            from reportlab.pdfbase.ttfonts import TTFont

            pdfmetrics.registerFont(TTFont("ThaiFont", str(thai_font)))
            self.thai_font = "ThaiFont"

    def _p(self, x: float, y: float) -> tuple[float, float]:
        return x * self._mm, (C.PAGE_HEIGHT_MM - y) * self._mm

    def _style(self, gray: int, lw: float) -> None:
        g = gray / 255.0
        self.c.setStrokeColorRGB(g, g, g)
        self.c.setFillColorRGB(g, g, g)
        self.c.setLineWidth(lw * self._mm)

    def rect(self, x0: float, y0: float, x1: float, y1: float, fill: bool, gray: int = 0, lw: float = 0.3) -> None:
        self._style(gray, lw)
        px, py = self._p(x0, y1)
        self.c.rect(px, py, (x1 - x0) * self._mm, (y1 - y0) * self._mm, stroke=0 if fill else 1, fill=1 if fill else 0)

    def circle(self, x: float, y: float, r: float, fill: bool, gray: int = 0, lw: float = 0.3) -> None:
        self._style(gray, lw)
        px, py = self._p(x, y)
        self.c.circle(px, py, r * self._mm, stroke=0 if fill else 1, fill=1 if fill else 0)

    def line(self, x0: float, y0: float, x1: float, y1: float, gray: int = 0, lw: float = 0.3) -> None:
        self._style(gray, lw)
        self.c.line(*self._p(x0, y0), *self._p(x1, y1))

    def text(self, x: float, y: float, s: str, pt: float, align: str = "left", gray: int = 0, bold: bool = False) -> None:
        self._style(gray, 0.1)
        if self.thai_font is not None and not s.isascii():
            # ฟอนต์ตระกูล TH Sarabun ตัวเล็กกว่า Helvetica ที่ขนาด pt เท่ากัน จึงขยาย
            pt *= C.THAI_FONT_SCALE
            self.c.setFont(self.thai_font, pt)
        else:
            self.c.setFont(self.font_bold if bold else self.font, pt)
        # y คือ baseline กึ่งกลางโดยประมาณ: เลื่อนลงครึ่งความสูงตัวอักษร
        px, py = self._p(x, y)
        py -= pt * 0.35
        if align == "center":
            self.c.drawCentredString(px, py, s)
        elif align == "right":
            self.c.drawRightString(px, py, s)
        else:
            self.c.drawString(px, py, s)

    def finish(self) -> None:
        self.c.showPage()
        self.c.save()


class PngBackend:
    """วาดลงภาพ numpy ขนาดเท่าภาพหลัง warp"""

    HERSHEY_CAP_PX_AT_SCALE1: float = 22.0
    PT_TO_CAP: float = 0.72  # ความสูงตัวพิมพ์ใหญ่เทียบขนาดฟอนต์

    def __init__(self) -> None:
        self.img = np.full((C.WARP_HEIGHT_PX, C.WARP_WIDTH_PX, 3), 255, np.uint8)

    @staticmethod
    def _p(x: float, y: float) -> tuple[int, int]:
        px, py = L.mm_to_px(x, y)
        return int(round(px)), int(round(py))

    @staticmethod
    def _lw(lw: float) -> int:
        return max(1, int(round(lw * L.S_AVG)))

    def rect(self, x0: float, y0: float, x1: float, y1: float, fill: bool, gray: int = 0, lw: float = 0.3) -> None:
        cv2.rectangle(self.img, self._p(x0, y0), self._p(x1, y1), (gray,) * 3, -1 if fill else self._lw(lw))

    def circle(self, x: float, y: float, r: float, fill: bool, gray: int = 0, lw: float = 0.3) -> None:
        cv2.circle(self.img, self._p(x, y), int(round(r * L.S_AVG)), (gray,) * 3, -1 if fill else self._lw(lw), cv2.LINE_AA)

    def line(self, x0: float, y0: float, x1: float, y1: float, gray: int = 0, lw: float = 0.3) -> None:
        cv2.line(self.img, self._p(x0, y0), self._p(x1, y1), (gray,) * 3, self._lw(lw), cv2.LINE_AA)

    def text(self, x: float, y: float, s: str, pt: float, align: str = "left", gray: int = 0, bold: bool = False) -> None:
        cap_px = pt / C.PDF_POINTS_PER_MM * L.S_AVG * self.PT_TO_CAP
        scale = cap_px / self.HERSHEY_CAP_PX_AT_SCALE1
        thick = max(1, int(round(scale * (2.2 if bold else 1.4))))
        font = cv2.FONT_HERSHEY_SIMPLEX
        (tw, th), _ = cv2.getTextSize(s, font, scale, thick)
        px, py = self._p(x, y)
        if align == "center":
            px -= tw // 2
        elif align == "right":
            px -= tw
        cv2.putText(self.img, s, (px, py + th // 2), font, scale, (gray,) * 3, thick, cv2.LINE_AA)


def find_thai_font() -> Path | None:
    """ค้นหาฟอนต์ไทยในเครื่อง (Sarabun / TH Sarabun New)"""
    dirs = [
        Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts",
        Path.home() / "AppData/Local/Microsoft/Windows/Fonts",
        Path("/usr/share/fonts"),
        Path("/usr/local/share/fonts"),
        Path.home() / ".fonts",
        Path("/Library/Fonts"),
        C.PROJECT_ROOT / "fonts",
    ]
    for d in dirs:
        if not d.is_dir():
            continue
        for name in THAI_FONT_FILES:
            hits = list(d.rglob(name))
            if hits:
                return hits[0]
    return None


def draw_sheet(b: Backend, text: dict[str, str], num_questions: int = C.NUM_QUESTIONS) -> None:
    """วาดองค์ประกอบทั้งหมดของกระดาษคำตอบลง backend"""
    # มาร์กเกอร์ 4 มุม (TL มีช่องขาว)
    for i, (x0, y0, x1, y1) in enumerate(L.marker_boxes_mm()):
        b.rect(x0, y0, x1, y1, fill=True)
        if i == 0:
            cx, cy, h = (x0 + x1) / 2, (y0 + y1) / 2, C.MARKER_HOLE_MM / 2
            b.rect(cx - h, cy - h, cx + h, cy + h, fill=True, gray=255)

    mid = C.PAGE_WIDTH_MM / 2
    b.text(mid, C.TITLE_Y_MM, text["title"], C.TITLE_FONT_PT, "center", bold=True)
    b.text(mid, C.SUBTITLE_Y_MM, text["subtitle"], C.SUBTITLE_FONT_PT, "center", gray=90)

    # ช่องข้อมูลผู้สอบ (ไม่อ่าน)
    for i, key in enumerate(("name", "subject", "section", "date")):
        y = C.INFO_FIRST_Y_MM + i * C.INFO_LINE_PITCH_MM
        b.text(C.INFO_LEFT_MM, y, text[key], C.BODY_FONT_PT)
        b.line(C.INFO_LEFT_MM + C.INFO_LABEL_WIDTH_MM, y + C.INFO_UNDERLINE_OFFSET_MM, C.INFO_LINE_END_MM,
               y + C.INFO_UNDERLINE_OFFSET_MM, gray=60, lw=0.2)

    # คำแนะนำ + ตัวอย่างการฝน
    y = C.INSTRUCTION_TOP_MM
    b.text(C.INFO_LEFT_MM, y, text["instr_head"], C.BODY_FONT_PT, bold=True)
    for i in range(1, 5):
        b.text(C.INFO_LEFT_MM, y + i * C.INSTRUCTION_LINE_PITCH_MM, text[f"instr{i}"], C.SMALL_FONT_PT, gray=40)
    ey = y + 5 * C.INSTRUCTION_LINE_PITCH_MM + C.EXAMPLE_ROW_OFFSET_MM
    er = C.EXAMPLE_BUBBLE_DIAMETER_MM / 2
    b.text(C.INFO_LEFT_MM, ey, text["correct"], C.SMALL_FONT_PT)
    b.circle(C.INFO_LEFT_MM + C.EXAMPLE_OK_X_MM, ey, er, fill=False, lw=C.BUBBLE_LINE_WIDTH_MM)
    b.circle(C.INFO_LEFT_MM + C.EXAMPLE_OK_X_MM, ey, er * 0.8, fill=True, gray=40)
    b.text(C.INFO_LEFT_MM + C.EXAMPLE_WRONG_LABEL_X_MM, ey, text["wrong"], C.SMALL_FONT_PT)
    for k, style in enumerate(("half", "tick", "cross")):
        ex = C.INFO_LEFT_MM + C.EXAMPLE_WRONG_X_MM + k * C.BUBBLE_PITCH_X_MM
        b.circle(ex, ey, er, fill=False, lw=C.BUBBLE_LINE_WIDTH_MM)
        if style == "half":
            b.rect(ex - er * 0.6, ey, ex + er * 0.6, ey + er * 0.6, fill=True, gray=40)
        elif style == "tick":
            b.line(ex - er * 0.6, ey, ex - er * 0.1, ey + er * 0.6, gray=40, lw=0.4)
            b.line(ex - er * 0.1, ey + er * 0.6, ex + er * 0.7, ey - er * 0.6, gray=40, lw=0.4)
        else:
            b.line(ex - er * 0.6, ey - er * 0.6, ex + er * 0.6, ey + er * 0.6, gray=40, lw=0.4)
            b.line(ex - er * 0.6, ey + er * 0.6, ex + er * 0.6, ey - er * 0.6, gray=40, lw=0.4)

    # บล็อกรหัสนักศึกษา
    id_cols = L.student_id_bubbles_mm()
    x0f, y0f, x1f, y1f = (v / s for v, s in zip(L.student_id_frame_px(), (L.SX, L.SY, L.SX, L.SY)))
    b.rect(x0f, y0f, x1f, y1f, fill=False, gray=60, lw=0.3)
    b.text((x0f + x1f) / 2, C.ID_LABEL_Y_MM, text["id"], C.SMALL_FONT_PT, "center", bold=True)
    for col in id_cols:
        cx = col[0][0]
        hw = C.ID_WRITE_BOX_WIDTH_MM / 2
        b.rect(cx - hw, C.ID_WRITE_BOX_TOP_MM, cx + hw, C.ID_WRITE_BOX_TOP_MM + C.ID_WRITE_BOX_HEIGHT_MM,
               fill=False, gray=60, lw=0.25)
        for d, (x, yy, r) in col.items():
            b.circle(x, yy, r, fill=False, lw=C.BUBBLE_LINE_WIDTH_MM)
            b.text(x, yy, str(d), C.BUBBLE_LABEL_FONT_PT, "center", gray=C.BUBBLE_LABEL_GRAY)

    # บล็อกคำตอบ
    b.line(C.ANSWER_REGION_LEFT_MM, C.ANSWER_SEPARATOR_Y_MM, C.ANSWER_REGION_RIGHT_MM, C.ANSWER_SEPARATOR_Y_MM,
           gray=150, lw=0.2)
    for q, row in L.answer_bubbles_mm(num_questions).items():
        ax, ay, ar = row[C.CHOICES[0]]
        b.text(ax - ar - C.QUESTION_NUMBER_GAP_MM, ay, f"{q}.", C.BODY_FONT_PT, "right", bold=True)
        for ch, (x, yy, r) in row.items():
            b.circle(x, yy, r, fill=False, lw=C.BUBBLE_LINE_WIDTH_MM)
            b.text(x, yy, ch, C.BUBBLE_LABEL_FONT_PT, "center", gray=C.BUBBLE_LABEL_GRAY)

    b.text(mid, C.FOOTER_Y_MM, text["footer"], C.SMALL_FONT_PT, "center", gray=110)


def generate_pdf_bytes(num_questions: int = C.NUM_QUESTIONS, use_thai: bool = True) -> bytes:
    """สร้างกระดาษคำตอบ PDF คืนค่าเป็น bytes"""
    font = find_thai_font() if use_thai else None
    buf = io.BytesIO()
    backend = PdfBackend(buf, font)
    draw_sheet(backend, TEXT_TH if font else TEXT_EN, num_questions)
    backend.finish()
    log.info("สร้าง PDF (ฟอนต์ไทย: %s)", font)
    return buf.getvalue()


def generate_png_image(num_questions: int = C.NUM_QUESTIONS) -> np.ndarray:
    """สร้างกระดาษคำตอบเป็นภาพ BGR ขนาด 1240×1754 (ข้อความอังกฤษเสมอ)"""
    backend = PngBackend()
    draw_sheet(backend, TEXT_EN, num_questions)
    return backend.img


def save_sheets(pdf_path: Path, png_path: Path | None = None, num_questions: int = C.NUM_QUESTIONS) -> None:
    """บันทึก PDF และ PNG ลงไฟล์"""
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    pdf_path.write_bytes(generate_pdf_bytes(num_questions))
    if png_path is not None:
        png_path.parent.mkdir(parents=True, exist_ok=True)
        ok, enc = cv2.imencode(".png", generate_png_image(num_questions))
        if not ok:
            raise OSError("บันทึก PNG ไม่สำเร็จ")
        png_path.write_bytes(enc.tobytes())
