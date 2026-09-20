"""ทดสอบการให้คะแนนและการอ่านไฟล์เฉลย"""

from __future__ import annotations

import pytest

from omr.errors import AnswerKeyError
from omr.grader import answer_key_to_csv, grade, manual_read, parse_answer_key
from omr.models import ReadResult


def rr(answer: str, status: str, conf: float = 1.0, uncertain: bool = False) -> ReadResult:
    return ReadResult(answer, status, conf, uncertain, {})


def test_score_basic() -> None:
    reads = {1: rr("A", "OK"), 2: rr("B", "OK"), 3: rr("C", "FAINT", 0.5, True), 4: rr("D", "OK")}
    key = {1: "A", 2: "C", 3: "C", 4: "D"}
    s = grade(reads, key)
    assert (s.score, s.total, s.percent) == (3, 4, 75.0)
    assert [q.is_correct for q in s.questions] == [True, False, True, True]
    assert s.n_uncertain == 1
    assert s.avg_confidence == pytest.approx((1 + 1 + 0.5 + 1) / 4)


def test_multi_and_blank_score_zero() -> None:
    reads = {1: rr("AB", "MULTI"), 2: rr("", "BLANK"), 3: rr("A", "OK")}
    s = grade(reads, {1: "A", 2: "B", 3: "A"})
    assert s.score == 1 and s.total == 3
    assert s.n_multi == 1 and s.n_blank == 1
    assert not s.questions[0].is_correct


def test_incomplete_key_skips_questions() -> None:
    reads = {q: rr("A", "OK") for q in range(1, 11)}
    s = grade(reads, {1: "A", 2: "B", 5: "A"})
    assert s.total == 3 and s.score == 2
    assert [q.number for q in s.questions] == [1, 2, 5]


def test_empty_key() -> None:
    s = grade({1: rr("A", "OK")}, {})
    assert s.total == 0 and s.percent == 0.0


def test_parse_key_roundtrip(tmp_path) -> None:
    key = {1: "A", 2: "D", 40: "B"}
    p = tmp_path / "key.csv"
    p.write_text(answer_key_to_csv(key), encoding="utf-8")
    assert parse_answer_key(p) == key
    assert parse_answer_key(answer_key_to_csv(key).encode("utf-8-sig")) == key


@pytest.mark.parametrize("content", ["q,a\n1,A\n", "question,answer\n1,E\n", "question,answer\n", "question,answer\nx,A\n"])
def test_parse_key_invalid(content: str) -> None:
    with pytest.raises(AnswerKeyError):
        parse_answer_key(content.encode())


def test_manual_read() -> None:
    assert manual_read("b").status == "OK"
    assert manual_read("CA").answer == "AC"
    assert manual_read("").status == "BLANK"
