"""ทดสอบการ export Excel: มีครบทุกชีต คอลัมน์ และอ่านกลับด้วย pandas ได้"""

from __future__ import annotations

import io

import pandas as pd
from openpyxl import load_workbook

from omr.exporter import (
    DETAIL_COLUMNS, KEY_COLUMNS, SHEET_DETAIL, SHEET_KEY, SHEET_STATS, SHEET_SUMMARY, STATS_COLUMNS,
    SUMMARY_COLUMNS, export_excel,
)
from omr.grader import grade
from omr.models import ReadResult, SheetResult


def _sheet(name: str, sid: str, answers: dict[int, tuple[str, str]], key: dict[int, str]) -> SheetResult:
    reads = {q: ReadResult(a, s, 0.9 if s == "OK" else 0.3, s != "OK", {}) for q, (a, s) in answers.items()}
    res = SheetResult(filename=name, student_id=sid, id_valid="?" not in sid, id_confidence=0.9)
    res.answer_reads = reads
    return grade(reads, key, res)


def test_export_excel_structure() -> None:
    key = {1: "A", 2: "B", 3: "C"}
    ok = _sheet("s1.jpg", "65001", {1: ("A", "OK"), 2: ("B", "OK"), 3: ("D", "OK")}, key)
    review = _sheet("s2.jpg", "650?1", {1: ("AB", "MULTI"), 2: ("", "BLANK"), 3: ("C", "FAINT")}, key)
    err = SheetResult(filename="bad.jpg", error="พบมาร์กเกอร์ 2 จาก 4 ตัว")
    data = export_excel([ok, review, err], key)

    xls = pd.read_excel(io.BytesIO(data), sheet_name=None)
    assert list(xls) == [SHEET_SUMMARY, SHEET_DETAIL, SHEET_STATS, SHEET_KEY]
    assert list(xls[SHEET_SUMMARY].columns) == SUMMARY_COLUMNS
    assert list(xls[SHEET_DETAIL].columns) == DETAIL_COLUMNS
    assert list(xls[SHEET_STATS].columns) == STATS_COLUMNS
    assert list(xls[SHEET_KEY].columns) == KEY_COLUMNS

    summary = xls[SHEET_SUMMARY]
    assert len(summary) == 3
    assert list(summary["สถานะ"]) == ["สำเร็จ", "ต้องตรวจสอบ", "ผิดพลาด"]
    assert summary.loc[0, "คะแนน"] == 2
    assert len(xls[SHEET_DETAIL]) == 6
    stats = xls[SHEET_STATS]
    assert stats.loc[0, "จำนวนตอบถูก"] == 1 and stats.loc[0, "ฝนซ้ำ"] == 1
    assert stats.loc[1, "ไม่ฝน"] == 1

    wb = load_workbook(io.BytesIO(data))
    ws = wb[SHEET_SUMMARY]
    assert ws.freeze_panes == "A2"
    zero = export_excel([_sheet("z.jpg", "01234", {1: ("A", "OK")}, key)], key)
    zws = load_workbook(io.BytesIO(zero))[SHEET_SUMMARY]
    assert zws["B2"].value == "01234" and zws["B2"].number_format == "@"
    assert ws["A1"].font.bold
    assert ws["A3"].fill.fgColor.rgb.endswith("FFF6C8")  # แถวต้องตรวจสอบ
    assert ws["A4"].fill.fgColor.rgb.endswith("F8D0D0")  # แถว error


def test_export_empty() -> None:
    xls = pd.read_excel(io.BytesIO(export_excel([], {1: "A"})), sheet_name=None)
    assert len(xls[SHEET_SUMMARY]) == 0 and len(xls[SHEET_KEY]) == 1
