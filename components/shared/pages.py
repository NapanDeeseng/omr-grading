"""ทะเบียนหน้าเว็บ: แต่ละ component คือหนึ่งหน้า (st.Page) ที่มี URL ของตัวเอง

    localhost:8501/              → components/dashboard/dashboard.py (หน้าเริ่มต้น)
    localhost:8501/upload        → components/upload/upload.py
    localhost:8501/result        → components/result/result.py
    localhost:8501/report        → components/report/report.py
    localhost:8501/export_excel  → components/export_excel/export_excel.py
    localhost:8501/setting       → components/setting/setting.py

เพิ่มหน้าใหม่: สร้าง components/<ชื่อ>/<ชื่อ>.py (มี render() และ `if __name__ == "__main__": render()`)
แล้วเพิ่มหนึ่งแถวใน PAGE_DEFS
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st

COMPONENTS_DIR = Path(__file__).resolve().parent.parent
DEFAULT_PAGE = "dashboard"

# (ชื่อโฟลเดอร์ = url_path, ชื่อเมนู, ไอคอน) เรียงตามลำดับในเมนู
PAGE_DEFS: list[tuple[str, str, str]] = [
    ("dashboard", "หน้าหลัก", ":material/home:"),
    ("upload", "อัปโหลดภาพ", ":material/photo_camera:"),
    ("result", "ผลการตรวจ", ":material/fact_check:"),
    ("report", "รายงาน", ":material/bar_chart:"),
    ("export_excel", "ส่งออก Excel", ":material/description:"),
    ("setting", "ตั้งค่า", ":material/settings:"),
]


def page_path(name: str) -> Path:
    """ไฟล์ของหน้า: components/<ชื่อ>/<ชื่อ>.py"""
    return COMPONENTS_DIR / name / f"{name}.py"


def make_pages() -> list[st.Page]:
    """สร้าง st.Page ทุกหน้า (เรียกใน app.py ทุก rerun)"""
    return [st.Page(page_path(name), title=title, icon=icon, url_path=name, default=name == DEFAULT_PAGE)
            for name, title, icon in PAGE_DEFS]


def go(name: str) -> None:
    """ไปหน้าอื่น เช่น go("result") — เรียกหลังกดปุ่ม (ห้ามใช้เป็น on_click)"""
    st.switch_page(page_path(name))
