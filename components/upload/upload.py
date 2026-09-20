"""หน้าอัปโหลดภาพ: ขั้นที่ 1 เฉลย → ขั้นที่ 2 อัปโหลดภาพ → เริ่มตรวจ"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from components.shared import widgets as W
from components.shared.pages import go
from components.shared.state import load_example_key, run_grading
from omr import config as C
from omr.errors import AnswerKeyError
from omr.grader import AnswerKey, answer_key_to_csv, parse_answer_key


def render() -> None:
    W.header("อัปโหลดภาพ", "กำหนดเฉลย แล้วอัปโหลดภาพถ่ายกระดาษคำตอบได้ครั้งละหลายแผ่น", "photo_camera")
    left, right = st.columns([1, 1], gap="medium")
    with left, st.container(key="card_key"):
        key_editor()
    with right, st.container(key="card_upload"):
        W.card_title("ขั้นที่ 2 · อัปโหลดภาพกระดาษคำตอบ", "add_photo_alternate")
        files = st.file_uploader("เลือกภาพ (JPG / PNG) ได้หลายไฟล์", type=["jpg", "jpeg", "png"],
                                 accept_multiple_files=True)
        has_key = bool(st.session_state.answer_key)
        if not has_key:
            st.warning("กรุณากำหนดเฉลยในขั้นที่ 1 ก่อนเริ่มตรวจ", icon=":material/info:")
        st.caption(f"YOLOv8n: {W.yolo_status() if st.session_state.settings['yolo'] else 'ปิดใช้งาน'}")
        if st.button("เริ่มตรวจ", icon=":material/play_arrow:", type="primary", disabled=not (has_key and files)):
            run_grading([(f.name, f.getvalue()) for f in files])
            st.success(f"ตรวจเสร็จ {len(files)} แผ่น", icon=":material/check_circle:")
        if st.session_state.results:
            if st.button("ดูผลที่หน้าหลัก", icon=":material/arrow_forward:"):
                go("dashboard")


def key_editor() -> None:
    """ขั้นที่ 1: เฉลย (อัปโหลด CSV / โหลดตัวอย่าง / กรอกในตาราง)"""
    W.card_title("ขั้นที่ 1 · กำหนดเฉลย", "key")
    up = st.file_uploader("อัปโหลดไฟล์เฉลย CSV (คอลัมน์ question,answer)", type=["csv"], key="key_upload")
    # แถวแนวนอน: ปุ่มกว้างตามข้อความ (ไม่ถูกตัด) ข้อความสรุปใช้พื้นที่ที่เหลือ
    row = st.container(horizontal=True, vertical_alignment="center", gap="medium")
    if up is not None and st.session_state.get("key_upload_name") != up.name:
        try:
            st.session_state.answer_key = parse_answer_key(up.getvalue())
            st.session_state.key_upload_name = up.name
            st.success(f"โหลดเฉลย {len(st.session_state.answer_key)} ข้อ", icon=":material/check_circle:")
        except AnswerKeyError as exc:
            st.error(str(exc))
    if row.button("โหลดเฉลยตัวอย่าง", icon=":material/playlist_add:", width="content"):
        st.session_state.answer_key = load_example_key()
        st.session_state.pop("key_editor_table", None)
        st.rerun()

    key: AnswerKey = st.session_state.answer_key
    df = pd.DataFrame({
        "ข้อ": list(range(1, C.NUM_QUESTIONS + 1)),
        "เฉลย": [key.get(q, None) for q in range(1, C.NUM_QUESTIONS + 1)],
    })
    edited = st.data_editor(
        df, hide_index=True, width="stretch", height=280, key="key_editor_table",
        column_config={
            "ข้อ": st.column_config.NumberColumn(disabled=True),
            "เฉลย": st.column_config.SelectboxColumn(options=list(C.CHOICES)),
        },
    )
    new_key = {int(r["ข้อ"]): str(r["เฉลย"]) for _, r in edited.iterrows() if r["เฉลย"] in C.CHOICES}
    if new_key != key:
        st.session_state.answer_key = new_key
    row.caption(f"มีเฉลยแล้ว {len(new_key)}/{C.NUM_QUESTIONS} ข้อ (ข้อที่ไม่มีเฉลยจะไม่นับคะแนน)")
    if new_key:
        st.download_button("บันทึกเฉลยเป็น CSV", answer_key_to_csv(new_key), "answer_key.csv", "text/csv",
                           icon=":material/download:")


# Streamlit รันไฟล์นี้เป็นหน้าหนึ่ง (st.Page) ด้วย __name__ == "__main__"; ตอน import ในเทสต์จะไม่วาดหน้า
if __name__ == "__main__":
    render()
