"""รายชื่อนักเรียน: จับคู่รหัสที่ฝนบนกระดาษคำตอบกับ ชื่อ-สกุล / ห้อง / เลขที่ เพื่อทำรายงานคะแนนรายห้อง

กระดาษคำตอบมีแค่รหัส 5 หลัก ชื่อนักเรียนจึงต้องมาจากไฟล์รายชื่อที่ครูเตรียมไว้ (CSV หรือ Excel)
หัวคอลัมน์ยืดหยุ่น: รับทั้งภาษาไทยและอังกฤษ และรับชื่อกับนามสกุลแยกคอลัมน์ได้
"""

from __future__ import annotations

import io
import re
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from omr import config as C
from omr.errors import OMRError


class RosterError(OMRError):
    """ไฟล์รายชื่อนักเรียนอ่านไม่ได้หรือไม่มีคอลัมน์ที่จำเป็น"""


@dataclass(frozen=True)
class Student:
    student_id: str
    name: str
    room: str = ""
    number: int | None = None  # เลขที่ในห้อง


Roster = dict[str, Student]

# ชื่อหัวคอลัมน์ที่รับได้ (เทียบแบบตัดช่องว่าง + ตัวพิมพ์เล็ก)
ID_HEADERS = ("รหัส", "รหัสนักเรียน", "รหัสนักศึกษา", "เลขประจำตัว", "studentid", "student_id", "id")
NAME_HEADERS = ("ชื่อสกุล", "ชื่อ-สกุล", "ชื่อ-นามสกุล", "ชื่อนามสกุล", "ชื่อ", "name", "fullname")
LAST_HEADERS = ("นามสกุล", "สกุล", "lastname", "surname")
ROOM_HEADERS = ("ห้อง", "ห้องเรียน", "ชั้น", "ชั้น/ห้อง", "room", "class")
NUMBER_HEADERS = ("เลขที่", "no", "no.", "number")

TEMPLATE_CSV = "เลขที่,รหัส,ชื่อ,นามสกุล,ห้อง\n1,00001,สมชาย,ใจดี,ม.3/1\n2,00002,สมหญิง,รักเรียน,ม.3/1\n"


def _norm(header: object) -> str:
    return re.sub(r"\s+", "", str(header)).lower()


def _find(columns: list[str], names: tuple[str, ...]) -> str | None:
    wanted = {_norm(n) for n in names}
    return next((c for c in columns if _norm(c) in wanted), None)


def normalize_id(value: object) -> str:
    """ทำรหัสให้เป็นตัวเลข 5 หลัก — Excel มักตัดเลข 0 นำหน้าทิ้ง (00123 → 123) หรือเก็บเป็น 123.0"""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    text = str(value).strip()
    if re.fullmatch(r"\d+\.0+", text):
        text = text.split(".")[0]
    text = re.sub(r"\D", "", text)
    return text.zfill(C.STUDENT_ID_DIGITS) if text else ""


def _read_table(source: bytes | str | Path, filename: str) -> pd.DataFrame:
    name = (filename or (str(source) if isinstance(source, (str, Path)) else "")).lower()
    data = Path(source).read_bytes() if isinstance(source, (str, Path)) else bytes(source)
    try:
        if name.endswith((".xlsx", ".xlsm", ".xls")):
            return pd.read_excel(io.BytesIO(data), dtype=str)
        for enc in ("utf-8-sig", "cp874"):  # cp874 = CSV ที่ Excel ภาษาไทยบันทึก
            try:
                return pd.read_csv(io.BytesIO(data), dtype=str, encoding=enc)
            except UnicodeDecodeError:
                continue
    except Exception as exc:  # noqa: BLE001 — ไฟล์เสียต้องขึ้นข้อความภาษาไทยให้ครูเข้าใจ
        raise RosterError(f"อ่านไฟล์รายชื่อไม่ได้: {exc}") from exc
    raise RosterError("อ่านไฟล์รายชื่อไม่ได้: ไม่รู้จักการเข้ารหัสตัวอักษร (บันทึกเป็น CSV UTF-8 แล้วลองใหม่)")


def parse_roster(source: bytes | str | Path, filename: str = "") -> Roster:
    """อ่านรายชื่อจาก CSV / Excel คืน {รหัส 5 หลัก: Student}"""
    df = _read_table(source, filename)
    cols = [str(c) for c in df.columns]
    df.columns = cols
    id_col = _find(cols, ID_HEADERS)
    name_col = _find(cols, NAME_HEADERS)
    if id_col is None or name_col is None:
        raise RosterError(f"ไฟล์รายชื่อต้องมีคอลัมน์ \"รหัส\" และ \"ชื่อ\" (พบ: {', '.join(cols) or 'ไม่มีหัวคอลัมน์'})")
    last_col = _find(cols, LAST_HEADERS)
    room_col = _find(cols, ROOM_HEADERS)
    num_col = _find(cols, NUMBER_HEADERS)

    def cell(row: pd.Series, col: str | None) -> str:
        v = row[col] if col else None
        return "" if v is None or (isinstance(v, float) and pd.isna(v)) else str(v).strip()

    roster: Roster = {}
    for _, row in df.iterrows():
        sid = normalize_id(row[id_col])
        if not sid:
            continue
        name = " ".join(p for p in (cell(row, name_col), cell(row, last_col)) if p)
        num = normalize_id(cell(row, num_col)).lstrip("0") if num_col else ""
        if sid in roster:
            raise RosterError(f"รหัส {sid} ซ้ำกันในไฟล์รายชื่อ ({roster[sid].name} และ {name})")
        roster[sid] = Student(sid, name, cell(row, room_col), int(num) if num else None)
    if not roster:
        raise RosterError("ไม่พบรายชื่อนักเรียนในไฟล์")
    return roster


def rooms(roster: Roster) -> list[str]:
    """รายชื่อห้องเรียงตามลำดับ (ห้องว่าง = ไม่ได้ระบุ อยู่ท้ายสุด)"""
    return sorted({s.room for s in roster.values()}, key=lambda r: (r == "", _natural(r)))


def _natural(text: str) -> list[object]:
    """เรียงแบบคนอ่าน: ม.3/2 มาก่อน ม.3/10"""
    return [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", text)]
