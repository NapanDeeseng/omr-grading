"""ส่งออกผลการตรวจเป็นไฟล์ Excel (openpyxl)"""

from __future__ import annotations

import io
import logging
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

from omr import config as C
from omr.grader import AnswerKey
from omr.models import STATUS_BLANK, STATUS_FAINT, STATUS_MULTI, STATUS_OK, SheetResult

log = logging.getLogger(__name__)

SHEET_SUMMARY = "สรุปคะแนน"
SHEET_DETAIL = "รายข้อ"
SHEET_STATS = "สถิติรายข้อ"
SHEET_KEY = "เฉลย"

SUMMARY_COLUMNS = ["ลำดับ", "รหัสนักศึกษา", "ชื่อไฟล์", "คะแนน", "เต็ม", "ร้อยละ", "ความมั่นใจเฉลี่ย",
                   "ข้อไม่มั่นใจ", "ข้อไม่ฝน", "ข้อฝนซ้ำ", "สถานะ", "หมายเหตุ"]
DETAIL_COLUMNS = ["รหัสนักศึกษา", "ข้อ", "คำตอบ", "เฉลย", "ผล", "สถานะ", "ความมั่นใจ(%)", "ปัญหาที่ตรวจพบ"]
STATS_COLUMNS = ["ข้อ", "เฉลย", "จำนวนตอบถูก", "ร้อยละตอบถูก", "จำนวน A", "จำนวน B", "จำนวน C", "จำนวน D",
                 "ไม่ฝน", "ฝนซ้ำ"]
KEY_COLUMNS = ["ข้อ", "เฉลย"]
TEXT_COLUMNS = {"รหัสนักศึกษา"}

STATUS_TH = {STATUS_OK: "ปกติ", STATUS_FAINT: "ฝนจาง", STATUS_MULTI: "ฝนซ้ำ", STATUS_BLANK: "ไม่ฝน"}

HEADER_FILL = PatternFill("solid", fgColor="1F3A5F")
HEADER_FONT = Font(bold=True, color="FFFFFF")
REVIEW_FILL = PatternFill("solid", fgColor="FFF6C8")
ERROR_FILL = PatternFill("solid", fgColor="F8D0D0")
MAX_COL_WIDTH = 60
MIN_COL_WIDTH = 8
WIDTH_PADDING = 3


def _write_table(ws: Worksheet, columns: list[str], rows: list[list[Any]], fills: list[PatternFill | None]) -> None:
    """เขียนตารางพร้อมหัวตาราง freeze และปรับความกว้างคอลัมน์"""
    ws.append(columns)
    for cell in ws[1]:
        cell.fill, cell.font = HEADER_FILL, HEADER_FONT
        cell.alignment = Alignment(horizontal="center", vertical="center")
    text_cols = [i for i, c in enumerate(columns) if c in TEXT_COLUMNS]
    for row, fill in zip(rows, fills):
        ws.append(row)
        cells = ws[ws.max_row]
        for i in text_cols:
            cells[i].number_format = "@"  # รหัสขึ้นต้นด้วย 0 ต้องเป็นข้อความ
        if fill is not None:
            for cell in cells:
                cell.fill = fill
    ws.freeze_panes = "A2"
    for idx, col in enumerate(columns, start=1):
        values = [col] + [r[idx - 1] for r in rows]
        # ตัวอักษรไทยแคบกว่าละติน ใช้ความยาวสตริงเป็นค่าประมาณ
        width = max(len(str(v)) if v is not None else 0 for v in values) + WIDTH_PADDING
        ws.column_dimensions[get_column_letter(idx)].width = max(MIN_COL_WIDTH, min(MAX_COL_WIDTH, width))


def _note(r: SheetResult) -> str:
    notes: list[str] = []
    if r.error:
        notes.append(r.error)
    else:
        if not r.id_valid:
            notes.append("อ่านรหัสนักศึกษาไม่ได้บางหลัก")
        if r.n_uncertain:
            notes.append(f"ไม่มั่นใจ {r.n_uncertain} ข้อ")
        if r.n_multi:
            notes.append(f"ฝนซ้ำ {r.n_multi} ข้อ")
        if r.rotated:
            notes.append("ภาพกลับหัว (หมุนอัตโนมัติ)")
        notes.extend(r.warnings)
        n_ai = sum(b.source == "yolo" for b in r.problem_boxes)
        if n_ai:
            notes.append(f"YOLOv8n พบบริเวณที่มีปัญหา {n_ai} จุด")
        if r.reviewed:
            notes.append("แก้ไขโดยผู้ตรวจ")
    return "; ".join(notes)


def export_excel(results: list[SheetResult], answer_key: AnswerKey) -> bytes:
    """สร้างไฟล์ Excel 4 ชีต คืนค่าเป็น bytes"""
    wb = Workbook()
    ws_sum = wb.active
    ws_sum.title = SHEET_SUMMARY

    rows, fills = [], []
    for i, r in enumerate(results, start=1):
        rows.append([
            i, r.student_id, r.filename, r.score if not r.error else None, r.total if not r.error else None,
            r.percent if not r.error else None, round(r.avg_confidence * 100, 1) if not r.error else None,
            r.n_uncertain, r.n_blank, r.n_multi, r.status_label, _note(r),
        ])
        fills.append(ERROR_FILL if r.error else REVIEW_FILL if r.needs_review else None)
    _write_table(ws_sum, SUMMARY_COLUMNS, rows, fills)

    ws_det = wb.create_sheet(SHEET_DETAIL)
    rows, fills = [], []
    for r in results:
        for q in r.questions:
            rows.append([
                r.student_id, q.number, q.answer, q.key, "ถูก" if q.is_correct else "ผิด",
                STATUS_TH.get(q.status, q.status) + (" (แก้ไข)" if q.edited else ""), round(q.confidence * 100, 1),
                q.problem,
            ])
            flagged = q.uncertain or q.status in (STATUS_MULTI, STATUS_BLANK)
            fills.append(REVIEW_FILL if flagged else None)
    _write_table(ws_det, DETAIL_COLUMNS, rows, fills)

    ws_stat = wb.create_sheet(SHEET_STATS)
    graded = [r for r in results if not r.error]
    rows = []
    for qn, key in sorted(answer_key.items()):
        answers = [q for r in graded for q in r.questions if q.number == qn]
        n = len(answers)
        correct = sum(q.is_correct for q in answers)
        counts = [sum(q.answer == ch and q.status in (STATUS_OK, STATUS_FAINT) for q in answers) for ch in C.CHOICES]
        rows.append([
            qn, key, correct, round(100.0 * correct / n, 1) if n else 0.0, *counts,
            sum(q.status == STATUS_BLANK for q in answers), sum(q.status == STATUS_MULTI for q in answers),
        ])
    _write_table(ws_stat, STATS_COLUMNS, rows, [None] * len(rows))

    ws_key = wb.create_sheet(SHEET_KEY)
    rows = [[q, a] for q, a in sorted(answer_key.items())]
    _write_table(ws_key, KEY_COLUMNS, rows, [None] * len(rows))

    buf = io.BytesIO()
    wb.save(buf)
    log.info("export Excel: %d แผ่น", len(results))
    return buf.getvalue()
