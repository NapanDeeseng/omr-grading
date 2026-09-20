"""หน้าตั้งค่า: ค่าเกณฑ์การอ่าน, เปิด/ปิด YOLOv8n, โหมด debug, ตรวจใหม่, ล้างข้อมูล"""

from __future__ import annotations

import streamlit as st

from components.shared import widgets as W
from components.shared.state import autosave, default_settings, run_grading, thresholds
from omr.pipeline import regrade


def render() -> None:
    W.header("ตั้งค่า", "ปรับค่าเกณฑ์การอ่านวงคำตอบ และการตรวจจับด้วย YOLOv8n", "settings")
    s = st.session_state.settings
    with st.container(key="card_settings"):
        W.card_title("เกณฑ์การอ่านคำตอบ", "tune")
        s["fill"] = st.slider("FILL_THRESHOLD — สัดส่วนหมึกขั้นต่ำที่นับว่าฝน", 0.10, 0.90, float(s["fill"]), 0.01)
        s["faint"] = st.slider("FAINT_THRESHOLD — ต่ำกว่านี้ถือว่าว่าง", 0.02, float(s["fill"]),
                               min(float(s["faint"]), float(s["fill"])), 0.01)
        s["confidence"] = st.slider("CONFIDENCE_THRESHOLD — ต่ำกว่านี้ถือว่าไม่มั่นใจ", 0.0, 1.0,
                                    float(s["confidence"]), 0.01)
        s["debug"] = st.checkbox("โหมด debug (บันทึกภาพระหว่างขั้นตอนลงโฟลเดอร์ debug/)", bool(s["debug"]))
        s["yolo"] = st.checkbox("ใช้ YOLOv8n ตรวจจับบริเวณที่มีปัญหา (มีผลกับการตรวจครั้งถัดไป)", bool(s["yolo"]))
        st.caption(f"สถานะ YOLOv8n: {W.yolo_status()}")
    st.write("")
    row = st.container(horizontal=True, gap="medium")  # ปุ่มกว้างตามข้อความ ขึ้นบรรทัดใหม่เมื่อจอแคบ
    if row.button("ตรวจใหม่ทั้งหมดด้วยค่าใหม่", icon=":material/refresh:", type="primary", disabled=not st.session_state.results):
        if s["debug"] and st.session_state.uploads:
            run_grading(list(st.session_state.uploads.items()))
        else:
            for r in st.session_state.results:
                regrade(r, st.session_state.answer_key, thresholds())
            autosave()  # (run_grading บันทึกให้เองอยู่แล้ว)
        st.success("ตรวจใหม่เรียบร้อย", icon=":material/check_circle:")
    if row.button("คืนค่าเริ่มต้น", icon=":material/restart_alt:"):
        st.session_state.settings = default_settings()
        st.rerun()
    if row.button("ล้างข้อมูลทั้งหมด", icon=":material/delete_sweep:"):
        st.session_state.results = []
        st.session_state.uploads = {}
        st.session_state.answer_key = {}
        st.session_state.current_sheet = 0
        st.session_state.pop("key_editor_table", None)
        st.success("ล้างข้อมูลแล้ว", icon=":material/check_circle:")


# Streamlit รันไฟล์นี้เป็นหน้าหนึ่ง (st.Page) ด้วย __name__ == "__main__"; ตอน import ในเทสต์จะไม่วาดหน้า
if __name__ == "__main__":
    render()
