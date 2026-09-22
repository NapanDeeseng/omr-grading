"""ชิ้นส่วน UI ที่ใช้หลายหน้า: หัวเรื่อง, การ์ด KPI, ตารางผลรายข้อ, ตัวเลือกแผ่น, ปุ่ม Excel"""

from __future__ import annotations

import html
from datetime import datetime

import cv2
import numpy as np
import pandas as pd
import streamlit as st

from components.shared import icons
from omr import detector
from omr.exporter import export_excel
from omr.models import STATUS_BLANK, STATUS_MULTI, QuestionResult, SheetResult

XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
FLAG_ROW_STYLE = "background-color: #fef2f2"
STATUS_CELL_STYLE = {"ok": "color: #15803d; font-weight: 600", "bad": "color: #b91c1c; font-weight: 600",
                     "flag": "color: #b45309; font-weight: 600"}
ERROR_HINT = (
    "คำแนะนำ: ถ่ายภาพให้เห็นสี่เหลี่ยมดำครบทั้ง 4 มุม วางกระดาษบนพื้นเรียบสีเข้ม "
    "ใช้แสงสว่างพอและไม่มีเงาทับมุม เอียงไม่เกิน 15° แล้วอัปโหลดใหม่"
)

# โทนสีของการ์ด/ป้าย: (สีไอคอนและตัวอักษร, สีพื้นไอคอน)
TONES = {
    "blue": ("#1d4ed8", "#e8effd"),
    "green": ("#15803d", "#e7f6ec"),
    "amber": ("#b45309", "#fdf3e3"),
    "red": ("#b91c1c", "#fdecec"),
    "gray": ("#52627a", "#eef2f7"),
}


def to_rgb(img: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(img, cv2.COLOR_BGR2RGB)


def yolo_status() -> str:
    """สถานะ YOLOv8n — โหลดโมเดลในเธรดพื้นหลังเพื่อไม่ให้หน้าเว็บค้างรอ import torch
    ถ้ายังไม่มีโมเดลจะตรวจไฟล์ใหม่ทุกครั้ง (จึงเห็นโมเดลที่เพิ่งเทรนเสร็จโดยไม่ต้องรีสตาร์ต)"""
    detector.preload()
    return detector.status()


def header(title: str, subtitle: str = "", icon: str = "") -> None:
    """แถบหัวเรื่องสีน้ำเงินด้านบนของทุกหน้า (icon = ชื่อ Material Symbol เช่น "home")"""
    sub = f'<div class="s">{html.escape(subtitle)}</div>' if subtitle else ""
    ico = f'<div class="i"><span class="msym">{icon}</span></div>' if icon else ""
    st.markdown(f'<div class="omr-header">{ico}<div><div class="t">{html.escape(title)}</div>{sub}</div></div>',
                unsafe_allow_html=True)


def card_title(text: str, icon: str = "") -> None:
    """หัวข้อการ์ด (icon = ชื่อ Material Symbol)"""
    ico = f'<span class="msym">{icon}</span>' if icon else ""
    st.markdown(f'<div class="card-title">{ico}{html.escape(text)}</div>', unsafe_allow_html=True)


def kpi(col, icon: str, tone: str, label: str, value: str, sub: str = "", sub_tone: str = "gray") -> None:
    """การ์ดตัวเลขหนึ่งใบ (ไอคอน + ชื่อ + ค่า + บรรทัดย่อย) — icon ดูใน icons.py, tone ดูใน TONES"""
    fg, bg = TONES[tone]
    col.markdown(
        f'<div class="kpi"><div class="kpi-icon" style="background:{bg};color:{fg}">{icons.svg(icon, 26)}</div>'
        f'<div class="kpi-body"><div class="kpi-label">{html.escape(label)}</div>'
        f'<div class="kpi-value">{html.escape(value)}</div>'
        f'<div class="kpi-sub" style="color:{TONES[sub_tone][0]}">{html.escape(sub)}</div></div></div>',
        unsafe_allow_html=True,
    )


def kpi_row(r: SheetResult) -> None:
    """การ์ด 3 ใบ: รหัสนักเรียน / คะแนน / ความมั่นใจเฉลี่ย"""
    c = st.columns(3)
    kpi(c[0], "id_card", "blue", "รหัสนักเรียน", r.student_id or "-",
        "อ่านได้ครบ" if r.id_valid else "ต้องตรวจสอบรหัส", "green" if r.id_valid else "red")
    kpi(c[1], "score", "blue", "คะแนน", f"{r.score} / {r.total}", f"คิดเป็น {r.percent:.1f}%")
    confident = r.n_uncertain == 0
    kpi(c[2], "shield" if confident else "alert", "green" if confident else "amber",
        "ความมั่นใจเฉลี่ย", f"{r.avg_confidence * 100:.0f}%",
        "ไม่มีข้อที่ไม่มั่นใจ" if confident else f"ไม่มั่นใจ {r.n_uncertain} ข้อ",
        "green" if confident else "red")


def status_chip(label: str, tone: str, icon: str) -> str:
    """ป้ายสถานะเล็ก (HTML) เช่น status_chip("ถูกต้อง", "green", "check")"""
    fg, bg = TONES[tone]
    return f'<span class="chip" style="color:{fg};background:{bg}">{icons.svg(icon, 16, 2)}{html.escape(label)}</span>'


def sheet_label(i: int, r: SheetResult) -> str:
    sid = r.student_id or "ไม่ทราบรหัส"
    return f"แผ่นที่ {i + 1} · {sid} · {r.filename} ({r.status_label})"


def select_sheet(results: list[SheetResult], key: str) -> int:
    """เลือกแผ่น — จำแผ่นที่เลือกไว้ข้ามหน้า"""
    cur = min(st.session_state.current_sheet, len(results) - 1)
    idx = st.selectbox("เลือกแผ่น", range(len(results)), index=cur, key=key,
                       format_func=lambda i: sheet_label(i, results[i]))
    st.session_state.current_sheet = idx
    return idx


def sheet_error(r: SheetResult) -> None:
    st.error(f"ตรวจแผ่นนี้ไม่สำเร็จ: {r.error}")
    st.info(ERROR_HINT)
    if r.original_preview is not None:
        st.image(to_rgb(r.original_preview), caption="ภาพต้นฉบับ", width=420)


def is_flagged(q: QuestionResult) -> bool:
    return q.uncertain or q.status in (STATUS_MULTI, STATUS_BLANK)


def status_kind(q: QuestionResult) -> str:
    """ok / bad / flag — ใช้เลือกสีในตาราง"""
    if is_flagged(q):
        return "flag"
    return "ok" if q.is_correct else "bad"


def status_text(q: QuestionResult) -> str:
    """สถานะรายข้อแบบสั้นสำหรับตาราง"""
    if is_flagged(q):
        return {STATUS_MULTI: "ฝนซ้ำ", STATUS_BLANK: "ไม่ฝน"}.get(q.status, "ไม่มั่นใจ")
    return "ถูกต้อง" if q.is_correct else "ผิด"


def answer_table(r: SheetResult, key: str) -> QuestionResult | None:
    """ตารางผลรายข้อ (แถวสีแดงอ่อน = ต้องตรวจสอบ) คลิกแถวเพื่อเลือก คืนข้อที่เลือก"""
    df = pd.DataFrame([{
        "ข้อ": q.number, "คำตอบที่ตรวจพบ": q.answer or "-", "เฉลย": q.key,
        "ความมั่นใจ": f"{q.confidence * 100:.0f}%", "สถานะ": status_text(q),
    } for q in r.questions])
    kinds = [status_kind(q) for q in r.questions]

    def row_style(row: pd.Series) -> list[str]:
        base = FLAG_ROW_STYLE if kinds[row.name] == "flag" else ""
        return [f"{base}; {STATUS_CELL_STYLE[kinds[row.name]]}" if col == "สถานะ" else base for col in row.index]

    event = st.dataframe(df.style.apply(row_style, axis=1), hide_index=True, width="stretch", height=430,
                         key=key, on_select="rerun", selection_mode="single-row")
    rows = event.selection.rows if event is not None else []
    if rows:
        return r.questions[rows[0]]
    return next((q for q in r.questions if is_flagged(q)), r.questions[0] if r.questions else None)


def excel_download(label: str, key: str, **kwargs) -> None:
    """ปุ่มดาวน์โหลด Excel (ปุ่มหลักสีน้ำเงิน) — ชีตแรกเป็นรายงานคะแนนรายห้องพร้อมชื่อนักเรียน"""
    from components.shared.state import exam_info, roster  # state import widgets ไม่ได้ (วนกัน) จึง import ตอนใช้

    exam = exam_info()
    data = export_excel(st.session_state.results, st.session_state.answer_key, roster(), exam)
    stem = "_".join(p for p in (exam.title, exam.room) if p) or "omr_results"
    stem = "".join(ch if ch.isalnum() or ch in " ._-" else "-" for ch in stem).strip() or "omr_results"
    st.download_button(label, data, f"{stem}_{datetime.now():%Y%m%d_%H%M}.xlsx", XLSX_MIME,
                       icon=":material/download:", key=key, type="primary", **kwargs)
