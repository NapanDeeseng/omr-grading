"""โหลดไฟล์ .css ของ component เข้าหน้าเว็บ"""

from __future__ import annotations

from pathlib import Path

import streamlit as st

BASE_CSS = Path(__file__).with_name("base.css")


def load_css(path: Path) -> None:
    """ฝัง CSS จากไฟล์ (อ่านใหม่ทุก rerun จึงแก้ไฟล์ .css แล้วเห็นผลทันที)

    ใช้ st.html เพราะเนื้อหาที่มีแต่ <style> จะไม่กินพื้นที่บนหน้า (st.markdown จะเว้นช่องว่างทุกครั้งที่เรียก)
    """
    st.html(f"<style>{path.read_text(encoding='utf-8')}</style>")
