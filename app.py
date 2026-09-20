"""OMR Grading Dashboard (Streamlit) — จุดเริ่มต้นของหน้าเว็บ

รัน: streamlit run app.py

ไฟล์นี้ทำแค่ตั้งค่าหน้าเว็บ วาดเมนู แล้วให้ st.navigation เปิดหน้าตาม URL
แต่ละหน้าคือไฟล์ใน components/<ชื่อ>/<ชื่อ>.py (ทะเบียนหน้าอยู่ใน components/shared/pages.py)
"""

from __future__ import annotations

import streamlit as st

from components.shared.pages import make_pages
from components.shared.state import init_state
from components.shared.styles import BASE_CSS, load_css
from components.sidebar import sidebar


def main() -> None:
    st.set_page_config(page_title="OMR Grading Dashboard", layout="wide", page_icon=":material/fact_check:")
    init_state()
    load_css(BASE_CSS)
    pages = make_pages()
    # ซ่อนเมนูอัตโนมัติของ Streamlit แล้วใช้เมนูที่ออกแบบเองใน components/sidebar
    current = st.navigation(pages, position="hidden")
    sidebar.render(pages, current)
    current.run()


if __name__ == "__main__":
    main()
