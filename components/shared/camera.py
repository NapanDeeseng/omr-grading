"""กล้องสแกนกระดาษแบบเต็มจอ (แทน st.camera_input ที่กรอบเล็ก เปิดกล้องหน้าก่อน และต้องกดหลายขั้น)

เลือกโหมด "ถ่ายด้วยกล้อง" แล้วกล้องหลังเปิดเต็มจอทันที มีกรอบเล็งสัดส่วนกระดาษ A4 แบบตอนสแกน QR จ่ายเงิน
หน้าตา/การทำงานอยู่ใน camera.js + camera.css (st.components.v2) ไฟล์นี้แค่ส่งค่าเข้าไปและแปลงภาพที่ได้กลับเป็น bytes
"""

from __future__ import annotations

import base64
import binascii
from pathlib import Path

import streamlit as st

_DIR = Path(__file__).parent


def arm(token_key: str) -> None:
    """เรียกจาก on_change ของตัวเลือกโหมด: นับรอบที่ผู้ใช้เพิ่งเลือกโหมดกล้อง กล้องจะเปิดเองครั้งเดียวต่อรอบ"""
    st.session_state[token_key] = st.session_state.get(token_key, 0) + 1


def scanner(key: str, *, title: str, hint: str, open_label: str, open_hint: str, multiple: bool,
            open_token: int = 0) -> bytes | None:
    """วาดปุ่มเปิดกล้อง และคืนภาพ JPEG ที่เพิ่งถ่ายในรอบนี้ (ไม่มีภาพใหม่ → None)

    multiple=True: ถ่ายต่อเนื่องได้หลายแผ่นโดยไม่ปิดกล้อง ทุกภาพที่ถ่ายทำให้หน้า rerun หนึ่งครั้ง
    open_token: เปลี่ยนค่าเมื่อไรกล้องเปิดเองทันที (ดู arm) — 0 = รอผู้ใช้กดปุ่ม
    """
    css = (_DIR / "camera.css").read_text(encoding="utf-8")
    # ลงทะเบียนทุก rerun ได้ (นิยามเดิมไม่เตือนซ้ำ) และอ่านไฟล์ใหม่ทุกครั้งจึงแก้ .js/.css แล้วเห็นผลทันที
    component = st.components.v2.component(
        "omr_scanner", css=css, js=(_DIR / "camera.js").read_text(encoding="utf-8"))
    result = component(
        key=key,
        data={"css": css, "title": title, "hint": hint, "open_label": open_label, "open_hint": open_hint,
              "multiple": multiple, "open_token": open_token},
        on_photo_change=lambda: None,
    )
    return decode_photo(result.get("photo") if result else None)


def decode_photo(data_url: object) -> bytes | None:
    """data:image/jpeg;base64,... → bytes (รูปแบบไม่ถูกต้อง → None)"""
    if not isinstance(data_url, str) or not data_url.startswith("data:image/") or "," not in data_url:
        return None
    try:
        return base64.b64decode(data_url.split(",", 1)[1], validate=True) or None
    except (binascii.Error, ValueError):
        return None
