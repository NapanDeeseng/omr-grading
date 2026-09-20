"""ทดสอบส่วนเสริม: ขอบกระดาษสำรอง (imutils), binarize (SciPy + scikit-image), แสงสะท้อน (regionprops),
การผูกกรอบ YOLO กับข้อ, และการบันทึก/เปิดผลเป็นไฟล์ (ไม่ใช้ฐานข้อมูล)"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest

from conftest import encode_jpg, place_on_background
from omr import config as C
from omr import detector, preprocess, quality, storage
from omr import layout as L
from omr.errors import PaperNotFoundError
from omr.grader import grade
from omr.models import ProblemBox, ReadResult, SheetResult
from omr.pipeline import apply_review, grade_image

KEY = {q: C.CHOICES[(q - 1) % len(C.CHOICES)] for q in range(1, C.NUM_QUESTIONS + 1)}


def _filled_sheet(blank: np.ndarray) -> np.ndarray:
    """กระดาษที่ฝนตามเฉลยทุกข้อ และรหัส 12345"""
    sheet = blank.copy()
    for q, row in L.answer_bubbles_px().items():
        x, y, r = row[KEY[q]]
        cv2.circle(sheet, (round(x), round(y)), round(r * 0.9), (70, 70, 70), -1)
    for col, d in zip(L.student_id_bubbles_px(), "12345"):
        x, y, r = col[int(d)]
        cv2.circle(sheet, (round(x), round(y)), round(r * 0.9), (70, 70, 70), -1)
    return sheet


def _hide_marker(sheet: np.ndarray, idx: int) -> np.ndarray:
    """ทาสีกระดาษทับมาร์กเกอร์ (จำลองนิ้ว/สิ่งของบังมุม)"""
    out = sheet.copy()
    cx, cy = L.marker_centers_px()[idx]
    half = int(L.marker_size_px())
    cv2.rectangle(out, (int(cx) - half, int(cy) - half), (int(cx) + half, int(cy) + half), (245, 245, 245), -1)
    return out


@pytest.mark.parametrize("hidden", [0, 2])
def test_paper_fallback_when_marker_hidden(blank_sheet: np.ndarray, hidden: int) -> None:
    img, _ = place_on_background(_hide_marker(_filled_sheet(blank_sheet), hidden), 6)
    res = grade_image(encode_jpg(img), KEY, "hidden.jpg", detect_problems=False)
    assert res.error is None, res.error
    assert res.used_paper_fallback and res.needs_review
    assert res.score == C.NUM_QUESTIONS
    assert res.student_id == "12345"
    assert any("ขอบกระดาษ" in w for w in res.warnings)


def test_find_paper_rejects_noise() -> None:
    noise = np.random.default_rng(0).integers(0, 255, (800, 600, 3), dtype=np.uint8)
    with pytest.raises(PaperNotFoundError):
        preprocess.find_paper(noise)


def test_warp_paper_output_size(blank_sheet: np.ndarray) -> None:
    img, _ = place_on_background(blank_sheet, -9)
    warped = preprocess.warp_paper(img, preprocess.find_paper(img))
    assert warped.shape[:2] == (C.WARP_HEIGHT_PX, C.WARP_WIDTH_PX)


def test_binarize_marks_ink_and_removes_speckle(blank_sheet: np.ndarray) -> None:
    sheet = _filled_sheet(blank_sheet)
    rng = np.random.default_rng(1)
    ys, xs = rng.integers(200, 1500, 400), rng.integers(100, 1100, 400)
    sheet[ys, xs] = 0  # จุดดำโดด 1 px
    binary = preprocess.binarize(sheet)
    assert binary.dtype == np.uint8 and set(np.unique(binary)) <= {0, 255}
    assert np.count_nonzero(binary[ys, xs]) < 0.2 * len(ys)  # ไม่มี SciPy จุดโดดเป็นหมึกทั้งหมด
    x, y, _ = L.answer_bubbles_px()[1][KEY[1]]
    assert binary[int(y), int(x)] == 255


def test_glare_detected_and_assigned_to_rows(blank_sheet: np.ndarray) -> None:
    sheet = cv2.cvtColor(cv2.cvtColor(blank_sheet, cv2.COLOR_BGR2GRAY), cv2.COLOR_GRAY2BGR)
    sheet = (sheet.astype(np.float32) * 0.8).astype(np.uint8)  # กระดาษเทา ~200
    x0, y0, x1, y1 = L.question_row_px(3)
    cv2.rectangle(sheet, (x0, y0), (x1, y1 + 60), (255, 255, 255), -1)
    warnings, boxes = quality.assess(sheet)
    assert len(boxes) == 1 and any("แสงสะท้อน" in w for w in warnings)
    detector.assign_questions(boxes)
    assert 3 in boxes[0].questions and 4 in boxes[0].questions
    _, none = quality.assess((sheet.astype(np.float32) * 0 + 255).astype(np.uint8))
    assert none == []  # ทั้งแผ่นสว่างเท่ากันไม่ใช่แสงสะท้อน


def test_problem_box_flags_question_until_reviewed() -> None:
    reads = {q: ReadResult(KEY[q], "OK", 1.0, False, {}) for q in (1, 2)}
    sheet = SheetResult(filename="x", id_valid=True)
    sheet.answer_reads = reads
    sheet.problem_boxes = detector.assign_questions(
        [ProblemBox("erasure", "รอยลบ", 0.9, L.question_row_px(2))], C.NUM_QUESTIONS)
    grade(reads, KEY, sheet)
    q2 = sheet.questions[1]
    assert q2.uncertain and q2.problem == "รอยลบ" and sheet.needs_review
    assert not sheet.questions[0].uncertain
    apply_review(sheet, KEY, {2: KEY[2]})
    assert not sheet.questions[1].uncertain and sheet.n_uncertain == 0 and not sheet.needs_review


def test_detect_without_model_returns_empty(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(detector, "_model", None)
    monkeypatch.setattr(detector.C, "YOLO_WEIGHTS", tmp_path / "missing.pt")
    assert detector.load_model(tmp_path / "missing.pt") is None
    assert "ไม่พบไฟล์โมเดล" in detector.status()


def test_session_roundtrip(blank_sheet: np.ndarray, tmp_path: Path) -> None:
    img, _ = place_on_background(_filled_sheet(blank_sheet), 4)
    ok = grade_image(encode_jpg(img), KEY, "a.jpg", detect_problems=False)
    ok.problem_boxes = [ProblemBox("glare", "แสงสะท้อน", 1.0, (1, 2, 3, 4), "quality", [5])]
    bad = grade_image(b"broken", KEY, "bad.jpg")
    folder = storage.save_session([ok, bad], KEY, "ห้อง 1/ภาค:ต้น", root=tmp_path)
    assert folder.parent == tmp_path and (folder / storage.EXCEL_FILE).is_file()

    results, key = storage.load_session(folder)
    assert key == KEY
    assert [r.filename for r in results] == ["a.jpg", "bad.jpg"]
    r = results[0]
    assert (r.student_id, r.score, r.total) == (ok.student_id, ok.score, ok.total)
    assert r.answer_reads[1].answer == ok.answer_reads[1].answer
    assert r.problem_boxes[0].box == (1, 2, 3, 4) and r.problem_questions == {5: "แสงสะท้อน"}
    assert r.warped_image is not None and r.annotated_image is not None
    assert results[1].error == bad.error

    listed = storage.list_sessions(tmp_path)
    assert [s["name"] for s in listed] == [folder.name] and listed[0]["sheets"] == 2
    storage.delete_session(folder, root=tmp_path)
    assert storage.list_sessions(tmp_path) == []
