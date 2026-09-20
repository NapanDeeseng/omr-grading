"""ทดสอบ pipeline ครบวงจรด้วยภาพสังเคราะห์ และกรณีภาพเสีย"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

import synth
from conftest import encode_jpg, place_on_background
from omr import config as C
from omr.pipeline import apply_exif_orientation, apply_review, grade_image, read_exif_orientation, regrade

KEY = {q: C.CHOICES[(q * 7) % len(C.CHOICES)] for q in range(1, C.NUM_QUESTIONS + 1)}


@pytest.fixture(scope="module")
def synthetic_sheets(blank_sheet: np.ndarray) -> list[tuple[bytes, str, dict[int, str]]]:
    rng = np.random.default_rng(2024)
    out = []
    for _ in range(5):
        img, sid, answers, _ = synth.synth_one(rng, blank_sheet, C.NUM_QUESTIONS)
        out.append((encode_jpg(img), sid, answers))
    return out


def test_synthetic_sheets_read_correctly(synthetic_sheets: list[tuple[bytes, str, dict[int, str]]]) -> None:
    for i, (data, sid, answers) in enumerate(synthetic_sheets):
        res = grade_image(data, KEY, f"synth_{i}.jpg")
        assert res.error is None, res.error
        assert res.student_id == sid
        assert res.id_valid
        got = {q: r.answer for q, r in res.answer_reads.items()}
        assert got == answers
        expected_score = sum(1 for q, a in answers.items() if a == KEY[q])
        assert res.score == expected_score and res.total == C.NUM_QUESTIONS
        assert res.annotated_image is not None and res.annotated_image.shape[:2] == (C.WARP_HEIGHT_PX, C.WARP_WIDTH_PX)
        assert res.processing_ms > 0


def test_upside_down_sheet(blank_sheet: np.ndarray) -> None:
    img, _ = place_on_background(blank_sheet, 7, upside_down=True)
    res = grade_image(encode_jpg(img), KEY, "flip.jpg")
    assert res.error is None and res.rotated
    assert res.n_blank == C.NUM_QUESTIONS and res.score == 0
    assert not res.id_valid and res.student_id == "?" * C.STUDENT_ID_DIGITS


@pytest.mark.parametrize("data,name", [
    (b"not an image at all", "broken.jpg"),
    (b"", "empty.png"),
    (b"\x00" * 100, "photo.heic"),
    (b"abc", "file.gif"),
])
def test_bad_input_returns_error(data: bytes, name: str) -> None:
    res = grade_image(data, KEY, name)
    assert res.error is not None and res.score == 0


def test_no_paper_returns_error() -> None:
    blank = np.full((800, 600, 3), 128, np.uint8)
    res = grade_image(encode_jpg(blank), KEY, "gray.jpg")
    assert res.error is not None and "มาร์กเกอร์" in res.error


def test_missing_file_returns_error(tmp_path: Path) -> None:
    res = grade_image(tmp_path / "nope.jpg", KEY)
    assert res.error is not None


def test_regrade_and_review(synthetic_sheets: list[tuple[bytes, str, dict[int, str]]]) -> None:
    data, sid, _ = synthetic_sheets[0]
    res = grade_image(data, KEY, "a.jpg")
    base_score = res.score
    new_key = {q: "A" for q in KEY}
    regrade(res, new_key)
    assert res.total == len(new_key)
    regrade(res, KEY)
    assert res.score == base_score
    wrong_q = next(q.number for q in res.questions if not q.is_correct)
    apply_review(res, KEY, {wrong_q: KEY[wrong_q]}, student_id="12345")
    assert res.score == base_score + 1
    assert res.reviewed and res.student_id == "12345" and res.id_valid
    assert next(q for q in res.questions if q.number == wrong_q).edited
    assert res.status_label == "สำเร็จ"


def test_exif_orientation(blank_sheet: np.ndarray) -> None:
    # สร้าง JPEG ที่มี APP1 EXIF orientation = 3 (180°)
    tiff = b"MM\x00*\x00\x00\x00\x08" + b"\x00\x01" + b"\x01\x12\x00\x03\x00\x00\x00\x01\x00\x03\x00\x00" + b"\x00" * 4
    app1 = b"Exif\x00\x00" + tiff
    img, _ = place_on_background(blank_sheet, 0)
    jpg = encode_jpg(img)
    data = jpg[:2] + b"\xff\xe1" + (len(app1) + 2).to_bytes(2, "big") + app1 + jpg[2:]
    assert read_exif_orientation(data) == 3
    assert read_exif_orientation(jpg) == 1
    small = np.arange(6, dtype=np.uint8).reshape(2, 3)
    assert np.array_equal(apply_exif_orientation(small, 3), small[::-1, ::-1])
    assert apply_exif_orientation(small, 6).shape == (3, 2)
    res = grade_image(data, KEY, "exif.jpg")
    assert res.error is None and res.rotated  # EXIF หมุน 180° แล้วตรวจทิศพบว่ากลับหัว
