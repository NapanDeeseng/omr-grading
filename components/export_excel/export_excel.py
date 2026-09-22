"""หน้าส่งออก Excel: ดาวน์โหลด Excel, บันทึกผลเป็นไฟล์, เปิด/ลบผลที่บันทึกไว้ (ไม่ใช้ฐานข้อมูล)"""

from __future__ import annotations

from datetime import datetime

import pandas as pd
import streamlit as st

from components.shared import widgets as W
from components.shared.state import roster as current_roster, save_results
from omr import config as C
from omr import storage
from omr.models import SheetResult
from omr.roster import TEMPLATE_CSV, RosterError, parse_roster, rooms


def render() -> None:
    sub = ("ดาวน์โหลดไฟล์ Excel เก็บไว้ในเครื่องของคุณ" if C.PUBLIC_MODE
           else "ดาวน์โหลดไฟล์ Excel และบันทึก/เปิดผลการตรวจที่เก็บไว้ในเครื่อง")
    W.header("ส่งออก Excel", sub, "description")
    results: list[SheetResult] = st.session_state.results
    with st.container(key="card_exam"):
        exam_section(results)
    st.space("small")
    if C.PUBLIC_MODE:
        # เว็บสาธารณะไม่เก็บไฟล์ไว้บนเซิร์ฟเวอร์ จึงไม่มีส่วน "บันทึกลงเครื่อง" และ "ผลที่บันทึกไว้"
        with st.container(key="card_excel"):
            W.card_title("ดาวน์โหลด Excel", "download")
            st.caption("4 ชีต: สรุปคะแนน (แถวเหลือง = ต้องตรวจสอบ) · รายข้อ · สถิติรายข้อ · เฉลย")
            if results:
                W.excel_download("ดาวน์โหลด Excel", "export_page")
            else:
                st.info("ยังไม่มีผลการตรวจ", icon=":material/info:")
            st.caption(":material/lock: ภาพและคะแนนอยู่ในเบราว์เซอร์ของคุณเท่านั้น ไม่ถูกเก็บบนเซิร์ฟเวอร์")
        return
    left, right = st.columns([1, 1], gap="medium")
    with left, st.container(key="card_excel"):
        W.card_title("ดาวน์โหลด Excel", "download")
        st.caption("4 ชีต: สรุปคะแนน (แถวเหลือง = ต้องตรวจสอบ) · รายข้อ · สถิติรายข้อ · เฉลย")
        if results:
            W.excel_download("ดาวน์โหลด Excel", "export_page")
        else:
            st.info("ยังไม่มีผลการตรวจ", icon=":material/info:")
        if C.PUBLIC_MODE:
            return
        st.divider()
        W.card_title("บันทึกผลการตรวจลงเครื่อง", "save")
        st.caption(f"เก็บเป็น JSON + Excel + ภาพ ใน {C.SESSIONS_DIR}")
        default = st.session_state.get("session_name") or f"ตรวจ_{datetime.now():%Y%m%d_%H%M}"
        name = st.text_input("ชื่อรอบการตรวจ", default)
        if st.button("บันทึก", icon=":material/save:", type="primary", disabled=not results):
            save_results(name)
    with right, st.container(key="card_history"):
        history_section()


def exam_section(results: list[SheetResult]) -> None:
    """ข้อมูลหัวรายงาน + รายชื่อนักเรียน → Excel ได้รายงานว่าห้องไหน นักเรียนชื่ออะไร ได้คะแนนเท่าไร"""
    W.card_title("ข้อมูลการสอบและรายชื่อนักเรียน", "groups")
    c1, c2, c3 = st.columns([2, 1, 1])
    c1.text_input("ชื่อการสอบ / วิชา", key="exam_title", placeholder="เช่น สอบกลางภาค คณิตศาสตร์ ม.3")
    c2.text_input("ห้อง", key="exam_room", placeholder="เช่น ม.3/1",
                  help="ใช้เมื่อไฟล์รายชื่อไม่มีคอลัมน์ห้อง ถ้ามีคอลัมน์ห้อง ระบบแยกชีตให้ห้องละชีตเอง")
    c3.date_input("วันที่สอบ", key="exam_date", format="DD/MM/YYYY")

    up = st.file_uploader("รายชื่อนักเรียน (CSV หรือ Excel: รหัส, ชื่อ, นามสกุล, ห้อง, เลขที่) — ไม่บังคับ",
                          type=["csv", "xlsx", "xls"], key="roster_upload")
    if up is not None and st.session_state.get("roster_name") != up.name:
        try:
            st.session_state.roster = parse_roster(up.getvalue(), up.name)
            st.session_state.roster_name = up.name
        except RosterError as exc:
            st.error(str(exc), icon=":material/error:")
    roster = current_roster()
    row = st.container(horizontal=True, vertical_alignment="center", gap="medium")
    row.download_button("ดาวน์โหลดแบบฟอร์มรายชื่อ", TEMPLATE_CSV.encode("utf-8-sig"), "แบบฟอร์มรายชื่อนักเรียน.csv",
                        "text/csv", icon=":material/table_view:")
    if not roster:
        row.caption("ไม่มีรายชื่อก็ส่งออกได้ แต่ Excel จะมีแค่รหัสนักเรียน ไม่มีชื่อ")
        return
    if row.button("ล้างรายชื่อ", icon=":material/close:"):
        st.session_state.roster = {}
        st.session_state.roster_name = None
        st.rerun()
    room_list = [r or "ไม่ระบุห้อง" for r in rooms(roster)]
    row.caption(f"รายชื่อ {len(roster)} คน · {len(room_list)} ห้อง ({', '.join(room_list[:6])}"
                f"{' …' if len(room_list) > 6 else ''})")
    if results:
        graded = [r for r in results if not r.error and r.id_valid]
        matched = sum(r.student_id in roster for r in graded)
        submitted = {r.student_id for r in graded}
        absent = sum(sid not in submitted for sid in roster)
        not_found = len(results) - matched
        msg = f"จับคู่ชื่อได้ {matched} จาก {len(results)} แผ่น · นักเรียนที่ไม่มีกระดาษคำตอบ {absent} คน"
        if not_found:
            st.warning(msg + f" · หาชื่อไม่เจอ {not_found} แผ่น (ดูชีต \"ตรวจสอบรหัส\" ใน Excel)",
                       icon=":material/warning:")
        else:
            st.success(msg, icon=":material/check_circle:")


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
