"""ทดสอบหน้าเว็บ: ทุกหน้าเป็นไฟล์ใน components/ ที่เปิดผ่าน st.navigation ได้ และ render โดยไม่มี exception"""

from __future__ import annotations

import importlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAGE_NAMES = ("dashboard", "upload", "result", "report", "export_excel", "setting")


def page_file(name: str) -> str:
    """path ของหน้า เทียบกับ app.py (รูปแบบที่ AppTest.switch_page ต้องการ)"""
    return f"components/{name}/{name}.py"


def test_components_registered_as_pages() -> None:
    app = importlib.import_module("app")
    assert callable(app.main)
    pages = importlib.import_module("components.shared.pages")
    # ทุกเมนูคือไฟล์ components/<ชื่อ>/<ชื่อ>.py และ url_path = ชื่อโฟลเดอร์
    assert [name for name, _, _ in pages.PAGE_DEFS] == list(PAGE_NAMES)
    for name in PAGE_NAMES:
        assert pages.page_path(name).is_file(), name
        module = importlib.import_module(f"components.{name}.{name}")
        assert callable(module.render), name
    state = importlib.import_module("components.shared.state")
    for name in ("init_state", "run_grading", "save_results", "load_example_key"):
        assert callable(getattr(state, name))
    assert len(state.load_example_key()) == 40
    for css in ("shared/base.css", "sidebar/sidebar.css", "dashboard/dashboard.css"):
        assert (ROOT / "components" / css).is_file(), css


def test_app_opens_main_page() -> None:
    from streamlit.testing.v1 import AppTest

    # เปิดเว็บแล้วเข้าหน้าหลักพร้อมเมนูทันที (ไม่มีหน้าต้อนรับ)
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=60).run()
    assert not at.exception and at.sidebar


def test_app_renders_all_pages() -> None:
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=60)
    at.run()
    assert not at.exception
    for name in (*PAGE_NAMES[1:], PAGE_NAMES[0]):
        at.switch_page(page_file(name)).run()
        assert not at.exception, f"หน้า {name}: {at.exception}"


def test_app_pages_with_results(blank_sheet) -> None:
    import numpy as np
    from streamlit.testing.v1 import AppTest

    import synth
    from conftest import encode_jpg
    from omr import config as C
    from omr.pipeline import grade_image

    key = {q: "A" for q in range(1, C.NUM_QUESTIONS + 1)}
    img, *_ = synth.synth_one(np.random.default_rng(7), blank_sheet, C.NUM_QUESTIONS)
    results = [grade_image(encode_jpg(img), key, "s1.jpg"), grade_image(b"broken", key, "bad.jpg")]

    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=60)
    at.session_state["answer_key"] = key
    at.session_state["results"] = results
    at.run()
    for name in PAGE_NAMES:
        at.switch_page(page_file(name)).run()
        assert not at.exception, f"หน้า {name}: {at.exception}"
    # ข้อมูลผลตรวจต้องคงอยู่เมื่อเปลี่ยนหน้า; เลือกแผ่นที่ error แล้วต้องแสดงข้อความ error
    at.switch_page(page_file("result")).run()
    at.selectbox[0].set_value(1).run()
    assert not at.exception and at.error
    # บันทึกการแก้ไขรหัส → สถานะแก้ไขโดยผู้ตรวจ
    at.selectbox[0].set_value(0).run()
    at.text_input[0].set_value("11111").run()
    at.button[0].click().run()
    assert not at.exception
    assert at.session_state["results"][0].reviewed
    assert at.session_state["results"][0].student_id == "11111"
