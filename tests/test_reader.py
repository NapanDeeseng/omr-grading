"""ทดสอบ read_group ทุกกรณีและ fill_ratio"""

from __future__ import annotations

import cv2
import numpy as np
import pytest

from omr import config as C
from omr.reader import combine_student_id, fill_ratio, read_group

TH = C.Thresholds()


def test_ok() -> None:
    r = read_group({"A": 0.05, "B": 0.92, "C": 0.03, "D": 0.04}, TH)
    assert (r.answer, r.status) == ("B", "OK")
    assert r.confidence == pytest.approx(1.0)
    assert not r.uncertain
    assert set(r.ratios) == {"A", "B", "C", "D"}


def test_ok_but_low_margin_is_uncertain() -> None:
    r = read_group({"A": 0.50, "B": 0.30, "C": 0.02, "D": 0.02}, TH)
    assert r.status == "OK" and r.answer == "A"
    assert r.confidence == pytest.approx((0.50 - 0.30) / C.CONFIDENCE_SCALE)
    assert r.uncertain


def test_faint() -> None:
    r = read_group({"A": 0.02, "B": 0.03, "C": 0.35, "D": 0.01}, TH)
    assert (r.answer, r.status) == ("C", "FAINT")
    assert r.confidence == pytest.approx((0.35 - 0.03) / C.CONFIDENCE_SCALE)
    assert r.uncertain  # ฝนจางต้อง flag เสมอ


def test_multi_keeps_choice_order() -> None:
    r = read_group({"A": 0.10, "B": 0.02, "C": 0.90, "D": 0.85}, TH)
    assert (r.answer, r.status) == ("CD", "MULTI")
    r = read_group({"A": 0.88, "B": 0.02, "C": 0.95, "D": 0.01}, TH)
    assert r.answer == "AC"
    assert r.uncertain  # r1-r2 ต่ำ


def test_blank() -> None:
    r = read_group({"A": 0.02, "B": 0.05, "C": 0.00, "D": 0.01}, TH)
    assert (r.answer, r.status) == ("", "BLANK")
    assert r.confidence == pytest.approx((C.FAINT_THRESHOLD - 0.05) / C.FAINT_THRESHOLD)
    assert not r.uncertain


def test_blank_near_threshold_is_uncertain() -> None:
    r = read_group({"A": 0.22, "B": 0.05, "C": 0.00, "D": 0.01}, TH)
    assert r.status == "BLANK" and r.uncertain


def test_custom_thresholds() -> None:
    th = C.Thresholds(fill=0.30, faint=0.10, confidence=0.5)
    r = read_group({"A": 0.35, "B": 0.0, "C": 0.0, "D": 0.0}, th)
    assert r.status == "OK"


def test_student_id_combine() -> None:
    reads = [read_group({str(d): (0.9 if d == v else 0.02) for d in range(10)}) for v in (6, 5, 0)]
    reads.append(read_group({str(d): 0.01 for d in range(10)}))
    reads.append(read_group({str(d): (0.9 if d == 1 else 0.02) for d in range(10)}))
    sid, valid, _ = combine_student_id(reads)
    assert sid == "650?1" and not valid


def test_fill_ratio() -> None:
    binary = np.zeros((100, 100), np.uint8)
    assert fill_ratio(binary, 50, 50, 15) == 0.0
    cv2.circle(binary, (50, 50), 20, 255, -1)
    assert fill_ratio(binary, 50, 50, 15) == pytest.approx(1.0)
    assert fill_ratio(binary, 2, 2, 15) == 0.0  # ออกนอกภาพ
    half = np.zeros((100, 100), np.uint8)
    half[:, 50:] = 255
    assert 0.4 < fill_ratio(half, 50, 50, 15) < 0.6
