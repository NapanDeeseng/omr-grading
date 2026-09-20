"""หน้าผลการตรวจ: ภาพที่วาดผลตรวจ, ปัญหาที่ YOLOv8n พบ, แก้ไขข้อที่ต้องตรวจสอบและรหัสนักศึกษา"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from components.shared import widgets as W
from omr import config as C
from omr.exporter import STATUS_TH
from omr.models import SheetResult
from components.shared.state import autosave
from omr.pipeline import apply_review

BLANK_OPTION = "(ว่าง)"


def render() -> None:
    W.header("ผลการตรวจ", "ดูผลรายแผ่น ภาพที่ระบบวาดผลตรวจ และแก้ไขข้อที่ระบบไม่มั่นใจ", "fact_check")
    results: list[SheetResult] = st.session_state.results
    if not results:
        st.info("ยังไม่มีผลการตรวจ — ไปที่เมนู 'อัปโหลดภาพ'", icon=":material/info:")
        return
    idx = W.select_sheet(results, "sheet_results")
    r = results[idx]
    if r.error:
        W.sheet_error(r)
        return
    W.kpi_row(r)
    st.write("")
    if r.reviewed:
        st.badge("แก้ไขโดยผู้ตรวจแล้ว", icon=":material/how_to_reg:", color="blue")
    for w in r.warnings:
        st.warning(w, icon=":material/warning:")
    ai = [b for b in r.problem_boxes if b.source == "yolo"]
    if ai:
        st.info(icon=":material/search:", body="YOLOv8n พบบริเวณที่มีปัญหา: " + ", ".join(
            f"{b.label} (ข้อ {', '.join(map(str, b.questions)) or '-'}, {b.score:.0%})" for b in ai))
    left, right = st.columns([1, 1], gap="medium")
    with left, st.container(key="card_review"):
        review_section(idx, r)
    with right, st.container(key="card_image"):
        W.card_title("ผลการตรวจบนกระดาษ", "image")
        if r.annotated_image is not None:
            st.image(W.to_rgb(r.annotated_image), width="stretch")
        st.caption("เขียว = ถูก · แดง = ผิด · เหลือง = ไม่มั่นใจ · กรอบส้ม = ฝนซ้ำ/ไม่ฝน · "
                   "กรอบม่วง = YOLOv8n · กรอบฟ้า = แสงสะท้อน")
        with st.expander("ภาพต้นฉบับ", icon=":material/photo:"):
            if r.original_preview is not None:
                st.image(W.to_rgb(r.original_preview), width="stretch")


def review_section(idx: int, r: SheetResult) -> None:
    """ฟอร์มแก้ไขคำตอบที่ต้องตรวจสอบ"""
    W.card_title("แก้ไขคำตอบที่ต้องตรวจสอบ", "edit_note")
    flagged = [q for q in r.questions if W.is_flagged(q) or q.edited]
    options = [BLANK_OPTION, *C.CHOICES]
    options += sorted({q.answer for q in flagged if q.answer and q.answer not in options})
    with st.form(f"review_{idx}", border=False):
        sid = st.text_input("รหัสนักศึกษา", r.student_id, max_chars=C.STUDENT_ID_DIGITS)
        edited = None
        if flagged:
            df = pd.DataFrame([{
                "ข้อ": q.number, "ระบบอ่านได้": q.answer or "-", "สถานะ": STATUS_TH.get(q.status, q.status),
                "ความมั่นใจ(%)": round(q.confidence * 100, 1), "ปัญหาที่ตรวจพบ": q.problem,
                "คำตอบที่ถูกต้อง": q.answer or BLANK_OPTION,
            } for q in flagged])
            edited = st.data_editor(df, hide_index=True, width="stretch", key=f"review_table_{idx}", column_config={
                "ข้อ": st.column_config.NumberColumn(disabled=True),
                "ระบบอ่านได้": st.column_config.TextColumn(disabled=True),
                "สถานะ": st.column_config.TextColumn(disabled=True),
                "ความมั่นใจ(%)": st.column_config.NumberColumn(disabled=True),
                "ปัญหาที่ตรวจพบ": st.column_config.TextColumn(disabled=True),
                "คำตอบที่ถูกต้อง": st.column_config.SelectboxColumn(options=options, help=f"{BLANK_OPTION} = ไม่ฝน"),
            })
        else:
            st.caption(":material/check_circle: ไม่มีข้อที่ต้องตรวจสอบ")
        if st.form_submit_button("บันทึกการแก้ไข", icon=":material/save:", type="primary"):
            edits: dict[int, str] = {}
            if edited is not None:
                edits = {int(row["ข้อ"]): "" if row["คำตอบที่ถูกต้อง"] in (None, BLANK_OPTION) else
                         str(row["คำตอบที่ถูกต้อง"]) for _, row in edited.iterrows()}
            apply_review(r, st.session_state.answer_key, edits, sid.strip())
            autosave()  # เก็บผลที่ผู้ตรวจแก้ลงไฟล์ทันที ไม่ต้องรอให้กด "บันทึกผล"
            st.success("บันทึกแล้ว คำนวณคะแนนใหม่เรียบร้อย", icon=":material/check_circle:")
            st.rerun()
    with st.expander("ผลรายข้อทั้งหมด", icon=":material/list_alt:"):
        W.answer_table(r, f"qtable_all_{idx}")


# Streamlit รันไฟล์นี้เป็นหน้าหนึ่ง (st.Page) ด้วย __name__ == "__main__"; ตอน import ในเทสต์จะไม่วาดหน้า
if __name__ == "__main__":
    render()
