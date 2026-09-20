"""หน้าหลัก: การ์ด KPI + ตารางผลรายข้อ + ภาพกระดาษและซูมข้อที่เลือก + ปุ่ม แก้ไขผล/บันทึกผล/Export Excel"""

from __future__ import annotations

import html
from pathlib import Path

import cv2
import numpy as np
import streamlit as st

from components.shared import widgets as W
from components.shared.pages import go
from components.shared.state import save_results
from components.shared.styles import load_css
from omr import config as C
from omr import layout as L
from omr.exporter import STATUS_TH
from omr.models import QuestionResult, SheetResult
from omr.sheet_generator import generate_pdf_bytes

ZOOM_PAD_X_PX, ZOOM_PAD_Y_PX, ZOOM_SCALE = 70, 12, 2.0  # ครอปแถวคำตอบ: ซ้ายรวมเลขข้อ, บน/ล่างเลยวง


@st.cache_data(show_spinner=False)
def sheet_pdf() -> bytes:
    return generate_pdf_bytes()


def render() -> None:
    load_css(Path(__file__).with_name("dashboard.css"))
    results: list[SheetResult] = st.session_state.results
    hero(results)
    if not results:
        welcome()
        return
    idx = W.select_sheet(results, "sheet_home")
    r = results[idx]
    if r.error:
        W.sheet_error(r)
        return
    W.kpi_row(r)
    st.write("")
    left, right = st.columns([1.15, 1], gap="medium")
    with left, st.container(key="card_table"):
        W.card_title("ผลการตรวจรายข้อ", "list_alt")
        chosen = W.answer_table(r, f"qtable_{idx}")
    with right, st.container(key="card_preview"):
        W.card_title("ภาพกระดาษคำตอบ", "image")
        thumb, zoom = st.columns([1, 1.25])
        if r.annotated_image is not None:
            thumb.image(W.to_rgb(r.annotated_image), width="stretch")
        with zoom:
            if chosen is not None:
                zoom_panel(r, chosen)
    for w in r.warnings:
        st.warning(w, icon=":material/warning:")
    st.space("small")
    # บอกให้ครูรู้ว่าผลถูกบันทึกให้อัตโนมัติแล้ว จะได้ไม่กังวลว่าปิดเบราว์เซอร์แล้วข้อมูลหาย
    if saved := st.session_state.get("autosaved"):
        st.caption(f":material/cloud_done: บันทึกอัตโนมัติแล้วที่ results/sessions/{saved} "
                   "(กด \"บันทึกผล\" อีกครั้งหลังแก้ไขผล เพื่อบันทึกทับ)")
    row = st.container(horizontal=True, horizontal_alignment="right", gap="small")
    if row.button("แก้ไขผล", icon=":material/edit:"):
        go("result")
    if row.button("บันทึกผล", icon=":material/save:"):
        save_results()
    with row:
        W.excel_download("ดาวน์โหลด Excel", "export_home")


# ---------------------------------------------------------------------------
# Hero banner
# ---------------------------------------------------------------------------
# ภาพประกอบ: กระดาษคำตอบที่มีวงฝนค่อย ๆ ถูกฝน เส้นสแกนวิ่งผ่าน และการ์ดผลลอยอยู่ข้าง ๆ
# (ข้อ, ตัวเลือกที่ฝน, ต้องตรวจสอบหรือไม่) — แถวที่ 4 ฝน 2 ตัวเลือกจึงเป็นวงสีเหลืองให้ตรวจ
_ART_ROWS = [(0, "B", False), (1, "D", False), (2, "A", False), (3, "AC", True), (4, "C", False), (5, "B", False)]


def _hero_art() -> str:
    bubbles = []
    for row, picks, flag in _ART_ROWS:
        y = 104 + row * 30
        bubbles.append(f'<text x="92" y="{y + 4}" class="qn">{row + 1}</text>')
        for j, ch in enumerate("ABCD"):
            x = 124 + j * 34
            bubbles.append(f'<circle cx="{x}" cy="{y}" r="10" class="ring{" warn" if flag else ""}"/>')
            if ch in picks:
                delay = 0.5 + row * 0.28 + j * 0.04
                bubbles.append(f'<circle cx="{x}" cy="{y}" r="7.5" class="dot{" warn" if flag else ""}" '
                               f'style="animation-delay:{delay:.2f}s"/>')
    return (
        '<div class="hero-art" aria-hidden="true">'
        '<svg viewBox="0 0 320 300" class="sheet">'
        '<defs><linearGradient id="scan" x1="0" x2="0" y1="0" y2="1">'
        '<stop offset="0" stop-color="#60a5fa" stop-opacity="0"/>'
        '<stop offset="1" stop-color="#60a5fa" stop-opacity=".55"/></linearGradient>'
        '<clipPath id="paper"><rect x="62" y="18" width="196" height="264" rx="16"/></clipPath></defs>'
        '<rect x="62" y="18" width="196" height="264" rx="16" class="paper"/>'
        '<rect x="80" y="36" width="12" height="12" rx="2" class="mark"/>'
        '<rect x="228" y="36" width="12" height="12" rx="2" class="mark"/>'
        '<rect x="102" y="38" width="80" height="7" rx="3.5" class="line"/>'
        '<rect x="102" y="52" width="54" height="5" rx="2.5" class="line soft"/>'
        '<rect x="80" y="70" width="160" height="1.5" class="line soft"/>'
        + "".join(bubbles) +
        '<g clip-path="url(#paper)"><rect x="62" y="0" width="196" height="46" fill="url(#scan)" class="scan"/></g>'
        '</svg>'
        '<div class="float-card fc-score"><span class="msym">workspace_premium</span>'
        '<div><small>คะแนน</small><b>38 / 40</b></div></div>'
        '<div class="float-card fc-check"><span class="msym">warning</span>'
        '<div><small>เตือนให้ตรวจ</small><b>ข้อ 4 ฝนซ้ำ</b></div></div>'
        '<div class="float-card fc-excel"><span class="msym">table_view</span><b>Excel พร้อมส่ง</b></div>'
        '</div>'
    )


def _hero_text(results: list[SheetResult]) -> str:
    if not results:
        eyebrow = "สำหรับครูและสถานศึกษา"
        title = 'ตรวจข้อสอบปรนัย<br><span class="accent">จากภาพถ่ายมือถือ</span>'
        sub = ("ถ่ายภาพกระดาษคำตอบ อัปโหลด แล้วรับคะแนนพร้อมไฟล์ Excel ทันที "
               "ข้อที่ระบบไม่แน่ใจจะถูกเตือนให้ครูตรวจซ้ำก่อนส่งออก")
        pills = [("bolt", "อ่านรหัสและคำตอบอัตโนมัติ"), ("verified", "เตือนข้อที่ต้องตรวจ"),
                 ("table_view", "ส่งออก Excel")]
    else:
        graded = [r for r in results if r.error is None]
        total = graded[0].total if graded else 0
        avg = sum(r.score for r in graded) / len(graded) if graded else 0.0
        n_review = sum(r.status_label == "ต้องตรวจสอบ" for r in results)
        n_error = len(results) - len(graded)
        eyebrow = "ภาพรวมการตรวจรอบนี้"
        title = f'ตรวจแล้ว {len(results)} แผ่น<br><span class="accent">คะแนนเฉลี่ย {avg:.1f} / {total}</span>'
        sub = "เลือกแผ่นด้านล่างเพื่อดูผลรายข้อ แก้ไขข้อที่ระบบไม่มั่นใจ แล้วดาวน์โหลด Excel"
        pills = [("task_alt", f"สำเร็จ {len(graded) - n_review} แผ่น"),
                 ("rule", f"ต้องตรวจสอบ {n_review} แผ่น")]
        if n_error:
            pills.append(("error", f"ตรวจไม่สำเร็จ {n_error} แผ่น"))
    pill_html = "".join(f'<span class="pill"><span class="msym">{i}</span>{html.escape(t)}</span>' for i, t in pills)
    return (f'<div class="hero-eyebrow"><span class="msym">school</span>{html.escape(eyebrow)}</div>'
            f'<div class="hero-title" role="heading" aria-level="1">{title}</div>'
            f'<p class="hero-sub">{html.escape(sub)}</p>'
            f'<div class="hero-pills">{pill_html}</div>')


def hero(results: list[SheetResult]) -> None:
    """แบนเนอร์ด้านบนหน้าหลัก: ข้อความ + ปุ่ม (ปุ่มจริงของ Streamlit) + ภาพประกอบเคลื่อนไหว"""
    with st.container(key="hero"):
        left, right = st.columns([1.25, 1], gap="large", vertical_alignment="center")
        with left:
            st.markdown(_hero_text(results), unsafe_allow_html=True)
            cta = st.container(horizontal=True, gap="small", key="hero_cta")
            if not results:
                if cta.button("เริ่มตรวจข้อสอบ", icon=":material/arrow_forward:", type="primary"):
                    go("upload")
                cta.download_button("ดาวน์โหลดกระดาษคำตอบ", sheet_pdf(), "answer_sheet.pdf", "application/pdf",
                                    icon=":material/download:")
            else:
                if cta.button("ตรวจเพิ่ม", icon=":material/add_a_photo:", type="primary"):
                    go("upload")
                if cta.button("ดูรายงาน", icon=":material/bar_chart:"):
                    go("report")
        with right:
            st.markdown(_hero_art(), unsafe_allow_html=True)


STEPS = [
    ("print", "พิมพ์กระดาษคำตอบ", "ดาวน์โหลด PDF แล้วพิมพ์ขนาดจริง 100% (ห้ามเลือก Fit to page)"),
    ("key", "กำหนดเฉลย", "อัปโหลดไฟล์ CSV หรือเลือกเฉลยในตารางทีละข้อ"),
    ("photo_camera", "ถ่ายภาพและอัปโหลด", "ถ่ายให้เห็นสี่เหลี่ยมดำครบ 4 มุม อัปโหลดได้ครั้งละหลายแผ่น"),
    ("fact_check", "ตรวจสอบและส่งออก", "แก้ข้อที่ระบบไม่มั่นใจ แล้วดาวน์โหลดคะแนนเป็น Excel"),
]


def welcome() -> None:
    """หน้าหลักเมื่อยังไม่มีผลตรวจ"""
    st.subheader("เริ่มต้นใช้งานใน 4 ขั้นตอน")
    # grid ที่ขึ้นแถวใหม่เองเมื่อจอแคบ (st.columns จะบีบการ์ดจนข้อความตกบรรทัดทีละคำ)
    cards = "".join(
        f'<div class="step"><div class="step-icon"><span class="msym">{icon}</span></div>'
        f'<div class="step-num">ขั้นที่ {i + 1}</div><div class="step-head">{html.escape(head)}</div>'
        f'<div class="step-body">{html.escape(body)}</div></div>'
        for i, (icon, head, body) in enumerate(STEPS))
    st.markdown(f'<div class="steps">{cards}</div>', unsafe_allow_html=True)
    st.space("small")
    with st.expander("รายละเอียดทางเทคนิค", icon=":material/info:"):
        st.caption(
            "ขั้นตอนประมวลผล: OpenCV หากระดาษ/มาร์กเกอร์ → imutils ปรับระนาบ → SciPy ลด noise → "
            "scikit-image adaptive threshold → อ่าน bubble → YOLOv8n ตรวจจับบริเวณที่มีปัญหา → "
            "Pandas/OpenPyXL ส่งออก Excel · เก็บผลเป็นไฟล์ ไม่ใช้ฐานข้อมูล")
        st.caption(f"YOLOv8n: {W.yolo_status()}")


def question_crop(r: SheetResult, q: QuestionResult) -> np.ndarray | None:
    """ครอปแถวคำตอบจากภาพผลตรวจแล้วขยาย"""
    img = r.annotated_image if r.annotated_image is not None else r.warped_image
    if img is None:
        return None
    x0, _, x1, _ = L.question_row_px(q.number)
    _, y, rad = next(iter(L.answer_bubbles_px()[q.number].values()))
    y0, y1 = int(y - rad) - ZOOM_PAD_Y_PX, int(y + rad) + ZOOM_PAD_Y_PX
    h, w = img.shape[:2]
    crop = img[max(0, y0): min(h, y1), max(0, x0 - ZOOM_PAD_X_PX): min(w, x1 + 10)]
    return cv2.resize(crop, None, fx=ZOOM_SCALE, fy=ZOOM_SCALE, interpolation=cv2.INTER_CUBIC)


def zoom_panel(r: SheetResult, q: QuestionResult) -> None:
    """ซูมข้อที่เลือก: ภาพจริง + bubble ที่อ่านได้ + ความมั่นใจ + ป้ายสถานะ"""
    st.markdown(f'<div class="zoom-q">ข้อ {q.number}</div>', unsafe_allow_html=True)
    crop = question_crop(r, q)
    if crop is not None:
        st.image(W.to_rgb(crop), width="stretch")
    bubbles = "".join(
        f'<div class="bubble{" on" if ch in q.answer else ""}{" key" if ch == q.key else ""}">{ch}</div>'
        for ch in C.CHOICES)
    conf_color = "#b91c1c" if q.uncertain else "#15803d"
    if W.is_flagged(q):
        badge = W.status_chip("ต้องตรวจสอบ", "amber", "alert")
    elif q.is_correct:
        badge = W.status_chip("ตอบถูก", "green", "check")
    else:
        badge = W.status_chip("ตอบผิด", "red", "cross")
    problem = f'<div class="conf">ปัญหาที่ตรวจพบ: <b>{html.escape(q.problem)}</b></div>' if q.problem else ""
    st.markdown(
        f'<div class="bubbles">{bubbles}</div>'
        f'<div class="conf">ความมั่นใจ <b style="color:{conf_color}">{q.confidence * 100:.0f}%</b>'
        f' · {STATUS_TH.get(q.status, q.status)}</div>{problem}<div class="badge-row">{badge}</div>',
        unsafe_allow_html=True,
    )
    st.caption("วงขอบเขียว = เฉลย · คลิกแถวในตารางเพื่อดูข้ออื่น")


# Streamlit รันไฟล์นี้เป็นหน้าหนึ่ง (st.Page) ด้วย __name__ == "__main__"; ตอน import ในเทสต์จะไม่วาดหน้า
if __name__ == "__main__":
    render()
