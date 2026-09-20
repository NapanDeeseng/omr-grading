"""ข้อมูลใน session_state และการกระทำที่หลายหน้าใช้ร่วมกัน (ตรวจภาพ, บันทึกผล, เปลี่ยนหน้า)"""

from __future__ import annotations

from datetime import datetime

import streamlit as st

from omr import config as C
from omr import storage
from omr.grader import AnswerKey, parse_answer_key
from omr.models import SheetResult
from omr.pipeline import grade_image

EXAMPLE_KEY_PATH = C.SAMPLES_DIR / "answer_key_example.csv"


def default_settings() -> dict:
    return {"fill": C.FILL_THRESHOLD, "faint": C.FAINT_THRESHOLD, "confidence": C.CONFIDENCE_THRESHOLD,
            "debug": C.DEBUG, "yolo": C.YOLO_ENABLED}


def init_state() -> None:
    """กำหนดค่าเริ่มต้นใน session_state"""
    st.session_state.setdefault("answer_key", {})
    st.session_state.setdefault("results", [])
    st.session_state.setdefault("uploads", {})  # ชื่อไฟล์ → bytes (ใช้ตรวจใหม่)
    st.session_state.setdefault("current_sheet", 0)
    st.session_state.setdefault("settings", default_settings())
    st.session_state.setdefault("is_demo", False)  # ผลชุดนี้มาจากภาพตัวอย่างหรือไม่
    st.session_state.setdefault("autosaved", "")  # ชื่อรอบที่บันทึกอัตโนมัติไว้ล่าสุด


def thresholds() -> C.Thresholds:
    s = st.session_state.settings
    return C.Thresholds(fill=s["fill"], faint=s["faint"], confidence=s["confidence"])


def load_example_key() -> AnswerKey:
    """โหลดเฉลยตัวอย่าง (สร้างแบบวนถ้าไม่มีไฟล์)"""
    if EXAMPLE_KEY_PATH.is_file():
        return parse_answer_key(EXAMPLE_KEY_PATH)
    return {q: C.CHOICES[(q - 1) % len(C.CHOICES)] for q in range(1, C.NUM_QUESTIONS + 1)}


def run_grading(items: list[tuple[str, bytes]]) -> None:
    """ตรวจภาพทั้งหมดพร้อม progress bar (ใช้ในหน้าอัปโหลดภาพและตั้งค่า)"""
    bar = st.progress(0.0, text="กำลังเริ่มตรวจ...")
    results: list[SheetResult] = []
    s = st.session_state.settings
    for i, (name, data) in enumerate(items):
        bar.progress(i / len(items), text=f"กำลังตรวจ {name} ({i + 1}/{len(items)})")
        st.session_state.uploads[name] = data
        results.append(grade_image(data, st.session_state.answer_key, name, thresholds(), debug=s["debug"],
                                   detect_problems=s["yolo"]))
    bar.progress(1.0, text="ตรวจเสร็จแล้ว")
    st.session_state.results = results
    st.session_state.current_sheet = 0
    autosave()


def autosave() -> None:
    """บันทึกผลอัตโนมัติทันทีที่ตรวจเสร็จ กันข้อมูลหายเมื่อปิดเบราว์เซอร์โดยยังไม่ได้กด "บันทึกผล"
    ใช้ชื่อรอบเดิมถ้าเคยบันทึกแล้ว (เขียนทับ) — เขียนไฟล์ไม่สำเร็จต้องไม่ทำให้ผลที่เพิ่งตรวจหาย
    โหมดสาธารณะไม่บันทึกอะไรลงเซิร์ฟเวอร์เลย (ข้อมูลนักเรียนของผู้ใช้คนอื่น)"""
    if C.PUBLIC_MODE:
        return
    try:
        folder = storage.save_session(st.session_state.results, st.session_state.answer_key,
                                      st.session_state.get("session_name")
                                      or f"ตรวจ_{datetime.now():%Y%m%d_%H%M}")
    except OSError as exc:
        st.session_state.autosaved = ""
        st.warning(f"บันทึกอัตโนมัติไม่สำเร็จ: {exc} — กรุณากด \"บันทึกผล\" หรือ Export Excel เก็บไว้เอง",
                   icon=":material/warning:")
        return
    st.session_state.session_name = folder.name
    st.session_state.autosaved = folder.name


def run_demo() -> None:
    """ตรวจภาพตัวอย่างที่มากับระบบ ให้คนที่ยังไม่มีกระดาษคำตอบเห็นผลได้ทันที"""
    st.session_state.answer_key = parse_answer_key(C.DEMO_KEY)
    st.session_state.is_demo = True
    run_grading([("ภาพตัวอย่าง.jpg", C.DEMO_IMAGE.read_bytes())])


def save_results(name: str = "") -> None:
    """บันทึกผลเป็นไฟล์ใน results/sessions (ใช้ในหน้าหลักและส่งออก Excel)"""
    folder = storage.save_session(st.session_state.results, st.session_state.answer_key,
                                  name or st.session_state.get("session_name") or f"ตรวจ_{datetime.now():%Y%m%d_%H%M}")
    st.session_state.session_name = folder.name
    st.toast(f"บันทึกแล้วที่ results/sessions/{folder.name}", icon=":material/save:")
