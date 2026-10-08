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


def test_autosave_writes_session(blank_sheet, tmp_path, monkeypatch) -> None:
    """ตรวจเสร็จแล้วต้องบันทึกไฟล์ให้เองทันที (กันข้อมูลหายเมื่อปิดเบราว์เซอร์ก่อนกด "บันทึกผล")"""
    import numpy as np
    from streamlit.testing.v1 import AppTest

    import synth
    from conftest import encode_jpg
    from omr import config as C
    from omr import storage

    sessions = tmp_path / "sessions"
    monkeypatch.setattr(C, "PUBLIC_MODE", False)
    monkeypatch.setattr(C, "SESSIONS_DIR", sessions)
    monkeypatch.setattr(storage.save_session, "__defaults__", ("", sessions))
    key = {q: "A" for q in range(1, C.NUM_QUESTIONS + 1)}
    img, *_ = synth.synth_one(np.random.default_rng(3), blank_sheet, C.NUM_QUESTIONS)
    data = encode_jpg(img)

    # โหมด debug ทำให้ปุ่ม "ตรวจใหม่ทั้งหมด" เรียก run_grading (เส้นทางเดียวกับการอัปโหลดภาพ)
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=60)
    at.session_state["answer_key"] = key
    at.run()
    at.session_state["results"] = [__import__("omr.pipeline", fromlist=["grade_image"]).grade_image(data, key, "s1.jpg")]
    at.session_state["uploads"] = {"s1.jpg": data}
    at.session_state["settings"]["debug"] = True
    at.switch_page(page_file("setting")).run()
    [regrade_btn] = [b for b in at.button if "ตรวจใหม่" in b.label]
    regrade_btn.click().run()

    saved = at.session_state["autosaved"]
    assert saved, "ตรวจเสร็จแล้วแต่ไม่ได้บันทึกอัตโนมัติ"
    assert (sessions / saved / "session.json").is_file()
    sheets, loaded_key = storage.load_session(sessions / saved)
    assert len(sheets) == 1 and loaded_key == key


def test_public_mode_keeps_nothing_on_server(blank_sheet, tmp_path, monkeypatch) -> None:
    """โหมดสาธารณะ (OMR_PUBLIC=1) ต้องไม่เขียนภาพ/คะแนนของนักเรียนลงเซิร์ฟเวอร์เลย"""
    import numpy as np
    from streamlit.testing.v1 import AppTest

    import synth
    from conftest import encode_jpg
    from omr import config as C
    from omr import storage
    from omr.pipeline import grade_image

    sessions = tmp_path / "sessions"
    monkeypatch.setattr(C, "PUBLIC_MODE", True)
    monkeypatch.setattr(C, "SESSIONS_DIR", sessions)
    monkeypatch.setattr(storage.save_session, "__defaults__", ("", sessions))
    key = {q: "A" for q in range(1, C.NUM_QUESTIONS + 1)}
    img, *_ = synth.synth_one(np.random.default_rng(5), blank_sheet, C.NUM_QUESTIONS)
    data = encode_jpg(img)

    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=60)
    at.session_state["answer_key"] = key
    at.run()
    at.session_state["results"] = [grade_image(data, key, "s1.jpg")]
    at.session_state["uploads"] = {"s1.jpg": data}
    at.session_state["settings"]["debug"] = True
    at.switch_page(page_file("setting")).run()
    [regrade_btn] = [b for b in at.button if "ตรวจใหม่" in b.label]
    regrade_btn.click().run()
    assert not at.exception
    assert not at.session_state["autosaved"] and not sessions.exists(), "โหมดสาธารณะต้องไม่เขียนไฟล์"

    # หน้าส่งออกต้องไม่มีปุ่มบันทึกลงเครื่อง เหลือแค่ดาวน์โหลด Excel
    at.switch_page(page_file("export_excel")).run()
    assert not at.exception
    assert not [b for b in at.button if "บันทึก" in b.label]


def test_demo_button_grades_sample_sheet() -> None:
    """ปุ่ม "ลองด้วยภาพตัวอย่าง" ต้องตรวจภาพที่มากับระบบและพาไปหน้าผลได้ (สำหรับคนที่ยังไม่มีกระดาษคำตอบ)"""
    from streamlit.testing.v1 import AppTest

    from omr import config as C

    assert C.DEMO_IMAGE.is_file() and C.DEMO_KEY.is_file(), "ไฟล์ตัวอย่างต้องมากับโปรเจกต์"
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=90)
    at.run()
    at.switch_page(page_file("upload")).run()
    [demo] = [b for b in at.button if "ภาพตัวอย่าง" in b.label]
    demo.click().run()
    assert not at.exception
    results = at.session_state["results"]
    assert len(results) == 1 and results[0].error is None
    assert results[0].student_id.isdigit(), "ต้องอ่านรหัสนักเรียนจากภาพตัวอย่างได้"
    assert results[0].score > 0


def test_new_batch_does_not_overwrite_saved_session(blank_sheet, tmp_path, monkeypatch) -> None:
    """ตรวจชุดใหม่ต้องไปโฟลเดอร์ใหม่ ห้ามเขียนทับรอบที่ครูบันทึก/เปิดค้างไว้ก่อนหน้า"""
    import numpy as np
    from streamlit.testing.v1 import AppTest

    import synth
    from conftest import encode_jpg
    from omr import config as C
    from omr import storage
    from omr.pipeline import grade_image

    sessions = tmp_path / "sessions"
    monkeypatch.setattr(C, "PUBLIC_MODE", False)
    monkeypatch.setattr(C, "SESSIONS_DIR", sessions)
    monkeypatch.setattr(storage.save_session, "__defaults__", ("", sessions))
    key = {q: "A" for q in range(1, C.NUM_QUESTIONS + 1)}
    old_img, *_ = synth.synth_one(np.random.default_rng(1), blank_sheet, C.NUM_QUESTIONS)
    new_img, *_ = synth.synth_one(np.random.default_rng(2), blank_sheet, C.NUM_QUESTIONS)

    old = [grade_image(encode_jpg(old_img), key, f"old{i}.jpg") for i in range(3)]
    storage.save_session(old, key, "รอบเก่าของครู")

    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=90)
    at.session_state["answer_key"] = key
    at.run()
    at.session_state["session_name"] = "รอบเก่าของครู"  # เหมือนเพิ่งกด "เปิด" รอบที่บันทึกไว้
    at.session_state["results"] = [grade_image(encode_jpg(new_img), key, "new.jpg")]
    at.session_state["uploads"] = {"new.jpg": encode_jpg(new_img)}
    at.session_state["settings"]["debug"] = True
    at.switch_page(page_file("setting")).run()
    [regrade_btn] = [b for b in at.button if "ตรวจใหม่" in b.label]
    regrade_btn.click().run()

    assert not at.exception
    assert len(storage.load_session(sessions / "รอบเก่าของครู")[0]) == 3, "รอบเก่าถูกเขียนทับ"
    assert at.session_state["autosaved"] != "รอบเก่าของครู"
    assert len(list(sessions.iterdir())) == 2


def test_camera_mode_grades_captured_sheets(blank_sheet, tmp_path, monkeypatch) -> None:
    """โหมดกล้อง: ภาพที่ถ่ายสะสมไว้หลายแผ่นถูกตรวจครบเมื่อกดเริ่มตรวจ และรายการที่ถ่ายถูกล้าง"""
    import hashlib

    import numpy as np
    from streamlit.testing.v1 import AppTest

    import synth
    from components.upload import upload
    from conftest import encode_jpg
    from omr import config as C
    from omr import storage

    monkeypatch.setattr(C, "SESSIONS_DIR", tmp_path / "sessions")
    monkeypatch.setattr(storage.save_session, "__defaults__", ("", tmp_path / "sessions"))
    key = {q: "A" for q in range(1, C.NUM_QUESTIONS + 1)}
    shots = [encode_jpg(synth.synth_one(np.random.default_rng(s), blank_sheet, C.NUM_QUESTIONS)[0]) for s in (21, 22)]

    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=90)
    at.session_state["answer_key"] = key
    at.session_state["image_source"] = upload.CAMERA
    at.run()
    # AppTest ยังสั่งกล้องไม่ได้ จึงใส่ภาพที่ "ถ่ายแล้ว" ลงรายการตรง ๆ (รูปแบบเดียวกับ _keep_capture)
    at.session_state["captures"] = [(f"กล้อง_{i}.jpg", d, hashlib.sha1(d).hexdigest()) for i, d in enumerate(shots)]
    at.switch_page(page_file("upload")).run()
    assert not at.exception
    [start] = [b for b in at.button if b.label.startswith("เริ่มตรวจ")]
    assert start.label == "เริ่มตรวจ 2 แผ่น" and not start.disabled
    start.click().run()

    assert not at.exception
    results = at.session_state["results"]
    assert len(results) == 2 and all(r.error is None for r in results)
    assert at.session_state["captures"] == [], "ตรวจแล้วต้องล้างรายการภาพที่ถ่าย เพื่อเริ่มชุดใหม่"


def test_export_page_matches_roster_names() -> None:
    """หน้าส่งออก Excel: ใส่รายชื่อแล้วบอกได้ว่าจับคู่ชื่อได้กี่แผ่น ขาดสอบกี่คน"""
    from streamlit.testing.v1 import AppTest

    from omr import config as C
    from omr.grader import parse_answer_key
    from omr.pipeline import grade_image
    from omr.roster import Student

    key = parse_answer_key(C.DEMO_KEY)
    demo = grade_image(C.DEMO_IMAGE.read_bytes(), key, "demo.jpg")
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=90)
    at.session_state["answer_key"] = key
    at.session_state["results"] = [demo]
    at.session_state["roster"] = {demo.student_id: Student(demo.student_id, "เด็กหญิงทดสอบ ตัวอย่าง", "ม.3/1", 1),
                                  "00001": Student("00001", "เด็กชายขาด สอบ", "ม.3/1", 2)}
    at.run()
    at.switch_page(page_file("export_excel")).run()
    assert not at.exception
    assert any("จับคู่ชื่อได้ 1 จาก 1 แผ่น" in s.value and "ไม่มีกระดาษคำตอบ 1 คน" in s.value for s in at.success)


def test_pages_survive_session_started_before_update(monkeypatch) -> None:
    """session ที่เปิดค้างไว้ตั้งแต่ก่อนอัปเดตโปรแกรม (init_state รุ่นเก่า ไม่มีคีย์ roster / exam_*)
    ต้องเปิดทุกหน้าและดาวน์โหลด Excel ได้ ไม่ขึ้น AttributeError"""
    from streamlit.testing.v1 import AppTest

    from components.shared import state
    from omr import config as C
    from omr.grader import parse_answer_key
    from omr.pipeline import grade_image

    new_keys = ("roster", "exam_title", "exam_room", "exam_date")
    original = state.init_state

    def old_init_state() -> None:
        original()
        for k in new_keys:
            st_state = __import__("streamlit").session_state
            if k in st_state:
                del st_state[k]

    monkeypatch.setattr(state, "init_state", old_init_state)
    key = parse_answer_key(C.DEMO_KEY)
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=90)
    at.session_state["answer_key"] = key
    at.session_state["results"] = [grade_image(C.DEMO_IMAGE.read_bytes(), key, "demo.jpg")]
    at.run()
    for name in PAGE_NAMES:
        at.switch_page(page_file(name)).run()
        assert not at.exception, f"หน้า {name}: {at.exception}"


def test_upload_page_key_photo_modes() -> None:
    from streamlit.testing.v1 import AppTest

    from components.upload import upload

    # ขั้นที่ 1 เลือกถ่าย/อัปโหลดภาพกระดาษเฉลยแทนไฟล์ CSV ได้
    for mode in (upload.KEY_IMAGE, upload.KEY_CAMERA):
        at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=60)
        at.session_state["key_source"] = mode
        at.run()
        at.switch_page(page_file("upload")).run()
        assert not at.exception, f"{mode}: {at.exception}"
