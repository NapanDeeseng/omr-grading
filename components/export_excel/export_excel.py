"""หน้าส่งออก Excel: ดาวน์โหลด Excel, บันทึกผลเป็นไฟล์, เปิด/ลบผลที่บันทึกไว้ (ไม่ใช้ฐานข้อมูล)"""

from __future__ import annotations

from datetime import datetime

import pandas as pd
import streamlit as st

from components.shared import widgets as W
from components.shared.state import save_results
from omr import config as C
from omr import storage
from omr.models import SheetResult


def render() -> None:
    W.header("ส่งออก Excel", "ดาวน์โหลดไฟล์ Excel และบันทึก/เปิดผลการตรวจที่เก็บไว้ในเครื่อง", "description")
    results: list[SheetResult] = st.session_state.results
    left, right = st.columns([1, 1], gap="medium")
    with left, st.container(key="card_excel"):
        W.card_title("ดาวน์โหลด Excel", "download")
        st.caption("4 ชีต: สรุปคะแนน (แถวเหลือง = ต้องตรวจสอบ) · รายข้อ · สถิติรายข้อ · เฉลย")
        if results:
            W.excel_download("ดาวน์โหลด Excel", "export_page")
        else:
            st.info("ยังไม่มีผลการตรวจ", icon=":material/info:")
        st.divider()
        W.card_title("บันทึกผลการตรวจลงเครื่อง", "save")
        st.caption(f"เก็บเป็น JSON + Excel + ภาพ ใน {C.SESSIONS_DIR}")
        default = st.session_state.get("session_name") or f"ตรวจ_{datetime.now():%Y%m%d_%H%M}"
        name = st.text_input("ชื่อรอบการตรวจ", default)
        if st.button("บันทึก", icon=":material/save:", type="primary", disabled=not results):
            save_results(name)
    with right, st.container(key="card_history"):
        history_section()


def history_section() -> None:
    """รายการผลที่บันทึกไว้ พร้อมปุ่มเปิด/ลบ"""
    W.card_title("ผลการตรวจที่บันทึกไว้", "history")
    sessions = storage.list_sessions()
    if not sessions:
        st.caption("ยังไม่มีผลที่บันทึกไว้")
        return
    st.dataframe(pd.DataFrame([{"ชื่อ": s["name"], "บันทึกเมื่อ": s["saved_at"].replace("T", " "),
                                "จำนวนแผ่น": s["sheets"]} for s in sessions]), hide_index=True, width="stretch")
    idx = st.selectbox("เลือกรอบการตรวจ", range(len(sessions)), format_func=lambda i: sessions[i]["name"])
    chosen = sessions[idx]
    c1, c2 = st.columns(2)
    if c1.button("เปิด", icon=":material/folder_open:", type="primary", width="stretch"):
        st.session_state.results, st.session_state.answer_key = storage.load_session(chosen["path"])
        st.session_state.session_name = chosen["name"]
        st.session_state.uploads = {}
        st.session_state.current_sheet = 0
        st.session_state.pop("key_editor_table", None)
        st.success(f"เปิด {chosen['name']} แล้ว ({len(st.session_state.results)} แผ่น)", icon=":material/check_circle:")
    if c2.button("ลบ", icon=":material/delete:", width="stretch"):
        storage.delete_session(chosen["path"])
        st.rerun()


# Streamlit รันไฟล์นี้เป็นหน้าหนึ่ง (st.Page) ด้วย __name__ == "__main__"; ตอน import ในเทสต์จะไม่วาดหน้า
if __name__ == "__main__":
    render()
