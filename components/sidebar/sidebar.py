"""เมนูด้านซ้าย: ลิงก์ไปแต่ละหน้า (URL เปลี่ยนตามหน้า เช่น /upload, /result)"""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from components.shared import icons
from components.shared.styles import load_css
from omr import __version__


def render(pages: list[st.Page], current: st.Page) -> None:
    """วาด sidebar และไฮไลต์หน้าที่เปิดอยู่ (ครอบด้วย container key=side_active ให้ CSS ทำสี)"""
    load_css(Path(__file__).with_name("sidebar.css"))
    with st.sidebar:
        st.markdown(f'<div class="side-brand"><div class="logo">{icons.svg("logo", 26)}</div>'
                    '<div class="name">ระบบตรวจข้อสอบ<small>ตรวจจากภาพถ่าย</small></div></div>',
                    unsafe_allow_html=True)
        st.markdown('<div class="side-label">เมนู</div>', unsafe_allow_html=True)
        with st.container(key="side_menu"):
            for page in pages:
                with st.container(key="side_active" if page.url_path == current.url_path else None):
                    st.page_link(page, width="stretch")
        st.space("small")
        st.markdown('<div class="side-label">สถานะ</div>'
                    f'<div class="side-stat">เฉลย<b>{len(st.session_state.answer_key)} ข้อ</b></div>'
                    f'<div class="side-stat">ตรวจแล้ว<b>{len(st.session_state.results)} แผ่น</b></div>',
                    unsafe_allow_html=True)
        st.caption(f"เวอร์ชัน {__version__}")
