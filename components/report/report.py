"""หน้ารายงาน: การ์ดสรุปทั้งห้อง, คำเตือนรหัสซ้ำ/อ่านไม่ได้, ตารางสรุป, กราฟ"""

from __future__ import annotations

from collections import Counter

import numpy as np
import pandas as pd
import streamlit as st

from components.shared import widgets as W
from omr.models import SheetResult


def summary_frame(results: list[SheetResult]) -> pd.DataFrame:
    """ตารางสรุปคะแนนรายแผ่น"""
    return pd.DataFrame([{
        "ลำดับ": i + 1, "รหัสนักศึกษา": r.student_id, "ชื่อไฟล์": r.filename,
        "คะแนน": None if r.error else r.score, "เต็ม": None if r.error else r.total,
        "ร้อยละ": None if r.error else r.percent,
        "ความมั่นใจเฉลี่ย(%)": None if r.error else round(r.avg_confidence * 100, 1),
        "ไม่มั่นใจ": r.n_uncertain, "ไม่ฝน": r.n_blank, "ฝนซ้ำ": r.n_multi,
        "สถานะ": ("แก้ไขโดยผู้ตรวจ" if r.reviewed and not r.error else r.status_label),
        "เวลา(ms)": r.processing_ms,
    } for i, r in enumerate(results)])


def render() -> None:
    W.header("รายงาน", "สรุปคะแนนทั้งห้อง การกระจายคะแนน และร้อยละตอบถูกรายข้อ", "bar_chart")
    results: list[SheetResult] = st.session_state.results
    if not results:
        st.info("ยังไม่มีผลการตรวจ", icon=":material/info:")
        return
    graded = [r for r in results if r.error is None]
    c = st.columns(4)
    W.kpi(c[0], "sheets", "blue", "จำนวนแผ่น", str(len(results)), f"สำเร็จ {len(graded)} แผ่น")
    if graded:
        scores = [r.score for r in graded]
        total = graded[0].total
        W.kpi(c[1], "chart", "blue", "คะแนนเฉลี่ย", f"{np.mean(scores):.1f}/{total}",
              f"สูงสุด {max(scores)} · ต่ำสุด {min(scores)}")
        W.kpi(c[2], "shield", "green", "ความมั่นใจเฉลี่ย",
              f"{np.mean([r.avg_confidence for r in graded]) * 100:.0f}%")
    n_review = sum(r.status_label != "สำเร็จ" for r in results)
    W.kpi(c[3], "alert" if n_review else "shield", "amber" if n_review else "green", "ต้องตรวจสอบ", str(n_review), "แผ่น")
    st.write("")

    ids = [r.student_id for r in graded]
    dup = sorted(k for k, v in Counter(ids).items() if v > 1)
    unreadable = [r.filename for r in graded if not r.id_valid]
    if dup:
        st.warning(f"พบรหัสนักศึกษาซ้ำ: {', '.join(dup)}", icon=":material/group:")
    if unreadable:
        st.warning(f"อ่านรหัสนักศึกษาไม่ได้ {len(unreadable)} แผ่น: {', '.join(unreadable)}", icon=":material/badge:")
    errors = [r.filename for r in results if r.error]
    if errors:
        st.error(f"ตรวจไม่สำเร็จ {len(errors)} แผ่น: {', '.join(errors)}", icon=":material/error:")

    with st.container(key="card_summary"):
        W.card_title("สรุปคะแนนรายแผ่น", "table_chart")
        st.dataframe(summary_frame(results), hide_index=True, width="stretch")
    if graded:
        st.write("")
        c1, c2 = st.columns(2, gap="medium")
        with c1, st.container(key="card_dist"):
            W.card_title("การกระจายคะแนน", "bar_chart")
            dist = pd.Series(Counter(r.score for r in graded)).sort_index()
            st.bar_chart(pd.DataFrame({"จำนวนคน": dist}), x_label="คะแนน", y_label="จำนวนคน")
        with c2, st.container(key="card_perq"):
            W.card_title("ร้อยละตอบถูกรายข้อ", "percent")
            per_q: dict[int, list[bool]] = {}
            for r in graded:
                for q in r.questions:
                    per_q.setdefault(q.number, []).append(q.is_correct)
            pct = pd.Series({q: 100 * np.mean(v) for q, v in sorted(per_q.items())})
            st.bar_chart(pd.DataFrame({"ร้อยละตอบถูก": pct}), x_label="ข้อ", y_label="ร้อยละ")


# Streamlit รันไฟล์นี้เป็นหน้าหนึ่ง (st.Page) ด้วย __name__ == "__main__"; ตอน import ในเทสต์จะไม่วาดหน้า
if __name__ == "__main__":
    render()
