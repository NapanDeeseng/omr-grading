"""ทดสอบ layout: bubble ไม่ทับกัน อยู่ในกระดาษ และจำนวนถูกต้อง"""

from __future__ import annotations

import itertools

import numpy as np
import pytest

from omr import config as C
from omr import layout as L


def _all_bubbles(num_q: int) -> list[tuple[float, float, float]]:
    answers = [b for row in L.answer_bubbles_mm(num_q).values() for b in row.values()]
    ids = [b for col in L.student_id_bubbles_mm() for b in col.values()]
    return answers + ids


@pytest.mark.parametrize("num_q", [1, 20, 25, 40, 60])
def test_bubbles_do_not_overlap(num_q: int) -> None:
    bubbles = _all_bubbles(num_q)
    pts = np.array([(x, y) for x, y, _ in bubbles])
    r = bubbles[0][2]
    d = np.sqrt(((pts[:, None, :] - pts[None, :, :]) ** 2).sum(-1))
    np.fill_diagonal(d, np.inf)
    assert d.min() > 2 * r, f"bubble ทับกัน ระยะต่ำสุด {d.min():.2f} mm"


@pytest.mark.parametrize("num_q", [1, 40, 60])
def test_bubbles_inside_page_and_clear_of_markers(num_q: int) -> None:
    boxes = L.marker_boxes_mm()
    clear = C.MARKER_CLEARANCE_MM
    for x, y, r in _all_bubbles(num_q):
        assert r <= x <= C.PAGE_WIDTH_MM - r and r <= y <= C.PAGE_HEIGHT_MM - r
        for x0, y0, x1, y1 in boxes:
            inside_x = x0 - clear - r < x < x1 + clear + r
            inside_y = y0 - clear - r < y < y1 + clear + r
            assert not (inside_x and inside_y), f"bubble ({x:.1f},{y:.1f}) ใกล้มาร์กเกอร์เกินไป"


@pytest.mark.parametrize("num_q", [1, 7, 20, 21, 40, 55, 60])
def test_counts_follow_config(num_q: int) -> None:
    ans = L.answer_bubbles_px(num_q)
    assert sorted(ans) == list(range(1, num_q + 1))
    assert all(list(row) == list(C.CHOICES) for row in ans.values())
    ids = L.student_id_bubbles_px()
    assert len(ids) == C.STUDENT_ID_DIGITS
    assert all(sorted(col) == list(C.DIGITS) for col in ids)


def test_invalid_question_count() -> None:
    with pytest.raises(ValueError):
        L.answer_bubbles_mm(C.MAX_QUESTIONS + 1)
    with pytest.raises(ValueError):
        L.answer_bubbles_mm(0)


def test_answer_block_below_id_block() -> None:
    id_bottom = max(y + r for col in L.student_id_bubbles_mm() for _, y, r in col.values())
    ans_top = min(y - r for row in L.answer_bubbles_mm(60).values() for _, y, r in row.values())
    assert ans_top > id_bottom


def test_marker_centers_px_order_and_symmetry() -> None:
    c = L.marker_centers_px()
    assert c.shape == (4, 2)
    tl, tr, br, bl = c
    assert tl[0] < tr[0] and tl[1] < bl[1] and br[0] > bl[0] and br[1] > tr[1]
    # หมุน 180° แล้วตำแหน่งมาร์กเกอร์ต้องทับกันพอดี (ใช้ตรวจทิศ)
    rotated = np.array([C.WARP_WIDTH_PX, C.WARP_HEIGHT_PX]) - c[[2, 3, 0, 1]]
    assert np.allclose(rotated, c, atol=1.0)


def test_pairs_have_no_duplicates() -> None:
    bubbles = _all_bubbles(60)
    assert len({(round(x, 3), round(y, 3)) for x, y, _ in bubbles}) == len(bubbles)
    assert all(a != b for a, b in itertools.pairwise(bubbles))
