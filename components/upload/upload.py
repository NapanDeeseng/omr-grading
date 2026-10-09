"""หน้าอัปโหลดภาพ: ขั้นที่ 1 เฉลย → ขั้นที่ 2 อัปโหลดภาพหรือถ่ายด้วยกล้อง → เริ่มตรวจ"""

from __future__ import annotations

import hashlib
from datetime import datetime

import pandas as pd
import streamlit as st

from components.shared import camera
from components.shared import widgets as W
from components.shared.pages import go
from components.shared.state import load_example_key, run_demo, run_grading, thresholds
from omr import config as C
from omr.errors import AnswerKeyError, OMRError
from omr.grader import AnswerKey, answer_key_to_csv, parse_answer_key
from omr.pipeline import heic_supported, read_key_image


def render() -> None:
    W.header("อัปโหลดภาพ", "กำหนดเฉลย แล้วอัปโหลดภาพหรือถ่ายกระดาษคำตอบด้วยกล้องได้ครั้งละหลายแผ่น", "photo_camera")
    left, right = st.columns([1, 1], gap="medium")
    with left, st.container(key="card_key"):
        key_editor()
    with right, st.container(key="card_upload"):
        W.card_title("ขั้นที่ 2 · เพิ่มภาพกระดาษคำตอบ", "add_photo_alternate")
        mode = st.segmented_control("วิธีเพิ่มภาพ", [UPLOAD, CAMERA], default=UPLOAD, key="image_source",
                                    label_visibility="collapsed", on_change=_arm_camera,
                                    args=("image_source", CAMERA, "camera_open")) or UPLOAD
        items = upload_items() if mode == UPLOAD else camera_items()
        has_key = bool(st.session_state.answer_key)
        if not has_key:
            st.warning("กรุณากำหนดเฉลยในขั้นที่ 1 ก่อนเริ่มตรวจ", icon=":material/info:")
        st.caption(f"YOLOv8n: {W.yolo_status() if st.session_state.settings['yolo'] else 'ปิดใช้งาน'}")
        label = f"เริ่มตรวจ {len(items)} แผ่น" if items else "เริ่มตรวจ"
        if st.button(label, icon=":material/play_arrow:", type="primary", disabled=not (has_key and items)):
            run_grading(items)
            if mode == CAMERA:
                st.session_state.captures = []  # ตรวจแล้ว เริ่มถ่ายชุดใหม่ได้เลย
            st.success(f"ตรวจเสร็จ {len(items)} แผ่น", icon=":material/check_circle:")
        if st.session_state.results:
            if st.button("ดูผลที่หน้าหลัก", icon=":material/arrow_forward:"):
                go("dashboard")
        st.divider()
        # ให้คนที่ยังไม่มีกระดาษคำตอบลองดูผลได้ทันที (ใช้เฉลยของภาพตัวอย่างเอง)
        st.caption("ยังไม่มีกระดาษคำตอบ? ลองด้วยภาพตัวอย่างได้เลย")
        if st.button("ลองด้วยภาพตัวอย่าง", icon=":material/science:", disabled=not C.DEMO_IMAGE.is_file()):
            run_demo()
            go("dashboard")
        if C.PUBLIC_MODE:
            st.caption(":material/lock: ภาพที่อัปโหลดใช้ตรวจในหน่วยความจำเท่านั้น ไม่ถูกเก็บไว้บนเซิร์ฟเวอร์")


NO_ANSWER = "—"  # แสดงในตารางเฉลยเมื่อยังไม่กำหนดข้อนั้น (Streamlit แสดงช่องว่างของ dropdown เป็นคำว่า "None")
UPLOAD = ":material/upload_file: อัปโหลดไฟล์"
CAMERA = ":material/photo_camera: ถ่ายด้วยกล้อง"
KEY_CSV = ":material/upload_file: ไฟล์ CSV"
KEY_IMAGE = ":material/image: ภาพกระดาษเฉลย"
KEY_CAMERA = ":material/photo_camera: ถ่ายด้วยกล้อง"


def image_types() -> list[str]:
    # HEIC จาก iPhone เปิดได้เมื่อติดตั้ง pillow-heif เท่านั้น จึงไม่โชว์ถ้าเครื่องนี้ยังไม่มี
    return ["jpg", "jpeg", "png"] + (["heic", "heif"] if heic_supported() else [])


def upload_items() -> list[tuple[str, bytes]]:
    types = image_types()
    files = st.file_uploader(f"เลือกภาพ ({' / '.join(t.upper() for t in types)}) ได้หลายไฟล์", type=types,
                             accept_multiple_files=True)
    st.caption("บนมือถือ กดปุ่มนี้แล้วเลือก \"ถ่ายรูป\" ได้เลย จะได้ภาพความละเอียดเต็มของกล้อง")
    return [(f.name, f.getvalue()) for f in files or []]


def _arm_camera(widget_key: str, camera_mode: str, token_key: str) -> None:
    """เพิ่งเลือกโหมดกล้อง → ให้กล้องเปิดเต็มจอเองทันที ไม่ต้องกดปุ่มซ้ำ"""
    if st.session_state.get(widget_key) == camera_mode:
        camera.arm(token_key)


def _keep_capture(data: bytes) -> None:
    """เก็บภาพที่เพิ่งถ่ายไว้ในรายการ — กล้องส่งมาทีละภาพ (ครั้งเดียวต่อการกดถ่าย) จึงสะสมเองเพื่อตรวจหลายแผ่นพร้อมกัน"""
    digest = hashlib.sha1(data).hexdigest()
    name = f"กล้อง_{datetime.now():%H%M%S}_{len(st.session_state.captures) + 1:02d}.jpg"
    st.session_state.captures.append((name, data, digest))


def camera_items() -> list[tuple[str, bytes]]:
    """ถ่ายต่อเนื่องทีละแผ่นด้วยกล้องเต็มจอ แล้วสะสมไว้จนกดเริ่มตรวจ"""
    shot = camera.scanner("sheet_scanner", title="สแกนกระดาษคำตอบ", multiple=True,
                          hint="ให้สี่เหลี่ยมดำทั้ง 4 มุมอยู่ในกรอบ แล้วกดถ่าย",
                          open_label="เปิดกล้องสแกน",
                          open_hint="ถ่ายกระดาษคำตอบต่อกันได้หลายแผ่น",
                          open_token=st.session_state.get("camera_open", 0))
    if shot:
        _keep_capture(shot)
    captures = st.session_state.captures
    if captures:
        row = st.container(horizontal=True, vertical_alignment="center", gap="small")
        row.markdown(f"**ถ่ายแล้ว {len(captures)} แผ่น**")
        if row.button("ลบแผ่นล่าสุด", icon=":material/undo:"):
            captures.pop()
            st.rerun()
        if row.button("ล้างทั้งหมด", icon=":material/delete_sweep:"):
            captures.clear()
            st.rerun()
        st.image([data for _, data, _ in captures], width=90, caption=[f"แผ่น {i + 1}" for i in range(len(captures))])
    st.caption("กล้องใช้ได้เมื่อเปิดเว็บผ่าน localhost หรือ https:// เท่านั้น (เบราว์เซอร์บล็อกกล้องบน http ธรรมดา) "
               "และเบราว์เซอร์จะถามสิทธิ์ใช้กล้องครั้งแรก — กด \"อนุญาต\"")
    return [(name, data) for name, data, _ in captures]


def key_from_csv() -> None:
    up = st.file_uploader("อัปโหลดไฟล์เฉลย CSV (คอลัมน์ question,answer)", type=["csv"], key="key_upload")
    if up is not None and st.session_state.get("key_upload_name") != up.name:
        try:
            st.session_state.answer_key = parse_answer_key(up.getvalue())
            st.session_state.key_upload_name = up.name
            st.session_state.pop("key_editor_table", None)  # ไม่งั้นค่าที่เคยแก้ในตารางจะทับเฉลยใหม่
            st.success(f"โหลดเฉลย {len(st.session_state.answer_key)} ข้อ", icon=":material/check_circle:")
        except AnswerKeyError as exc:
            st.error(str(exc))


def _read_key_photo(data: bytes, name: str) -> None:
    """อ่านเฉลยจากภาพครั้งเดียวต่อภาพ — ทุกครั้งที่แตะตาราง Streamlit จะ rerun แต่ต้องไม่อ่านภาพเดิมซ้ำทับที่ครูแก้ไว้"""
    digest = hashlib.sha1(data).hexdigest()
    if st.session_state.get("key_photo_digest") == digest:
        return
    st.session_state.key_photo_digest = digest
    try:
        key, review = read_key_image(data, name, thresholds())
    except OMRError as exc:
        st.session_state.key_photo_note = ("error", str(exc))
        return
    st.session_state.answer_key = key
    st.session_state.pop("key_editor_table", None)
    msg = f"อ่านเฉลยจากภาพได้ {len(key)} ข้อ"
    if review:
        msg += f" — ข้อ {', '.join(map(str, review))} ฝนหลายช่องหรือไม่ชัด กรุณาตรวจ/เลือกเฉลยในตารางด้านล่าง"
    st.session_state.key_photo_note = ("warning" if review else "success", msg)


def key_from_photo(mode: str) -> None:
    """ฝนเฉลยลงกระดาษคำตอบเปล่าหนึ่งแผ่น แล้วถ่าย/อัปโหลดภาพให้ระบบอ่านเป็นเฉลย"""
    if mode == KEY_CAMERA:
        shot = camera.scanner("key_scanner", title="สแกนกระดาษเฉลย", multiple=False,
                              hint="ให้สี่เหลี่ยมดำทั้ง 4 มุมอยู่ในกรอบ แล้วกดถ่าย",
                              open_label="เปิดกล้องสแกน", open_hint="ถ่ายกระดาษที่ฝนเฉลยไว้ 1 แผ่น",
                              open_token=st.session_state.get("key_camera_open", 0))
        if shot:
            _read_key_photo(shot, "เฉลย.jpg")
    else:
        up = st.file_uploader("เลือกภาพกระดาษคำตอบที่ฝนเฉลยไว้", type=image_types(), key="key_photo")
        st.caption("บนมือถือ กดปุ่มนี้แล้วเลือก \"ถ่ายรูป\" ได้เลย")
        if up is not None:
            _read_key_photo(up.getvalue(), up.name)
    note = st.session_state.get("key_photo_note")
    if note:
        kind, msg = note
        icon = {"error": ":material/error:", "warning": ":material/warning:"}.get(kind, ":material/check_circle:")
        getattr(st, kind)(msg, icon=icon)


def key_editor() -> None:
    """ขั้นที่ 1: เฉลย (อัปโหลด CSV / ถ่ายกระดาษเฉลย / โหลดตัวอย่าง / กรอกในตาราง)"""
    W.card_title("ขั้นที่ 1 · กำหนดเฉลย", "key")
    mode = st.segmented_control("วิธีกำหนดเฉลย", [KEY_CSV, KEY_IMAGE, KEY_CAMERA], default=KEY_CSV,
                                key="key_source", label_visibility="collapsed", on_change=_arm_camera,
                                args=("key_source", KEY_CAMERA, "key_camera_open")) or KEY_CSV
    if mode == KEY_CSV:
        key_from_csv()
    else:
        key_from_photo(mode)
    # แถวแนวนอน: ปุ่มกว้างตามข้อความ (ไม่ถูกตัด) ข้อความสรุปใช้พื้นที่ที่เหลือ
    row = st.container(horizontal=True, vertical_alignment="center", gap="medium")
    if row.button("โหลดเฉลยตัวอย่าง", icon=":material/playlist_add:", width="content"):
        st.session_state.answer_key = load_example_key()
        st.session_state.pop("key_editor_table", None)
        st.rerun()

    key: AnswerKey = st.session_state.answer_key
    df = pd.DataFrame({
        "ข้อ": list(range(1, C.NUM_QUESTIONS + 1)),
        "เฉลย": [key.get(q, NO_ANSWER) for q in range(1, C.NUM_QUESTIONS + 1)],
    })
    edited = st.data_editor(
        df, hide_index=True, width="stretch", height=280, key="key_editor_table",
        column_config={
            "ข้อ": st.column_config.NumberColumn(disabled=True),
            "เฉลย": st.column_config.SelectboxColumn(options=[NO_ANSWER, *C.CHOICES], required=True),
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
