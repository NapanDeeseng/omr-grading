"""เทียบคำตอบกับเฉลย ให้คะแนน และสรุปสถิติของแผ่น"""

from __future__ import annotations

import csv
import io
import logging
from pathlib import Path

from omr import config as C
from omr.errors import AnswerKeyError
from omr.models import STATUS_BLANK, STATUS_FAINT, STATUS_MULTI, STATUS_OK, QuestionResult, ReadResult, SheetResult

log = logging.getLogger(__name__)

AnswerKey = dict[int, str]


def parse_answer_key(source: str | Path | bytes) -> AnswerKey:
    """อ่านเฉลยจาก CSV (คอลัมน์ question,answer) รับ path หรือ bytes"""
    if isinstance(source, bytes):
        text = source.decode("utf-8-sig")
    elif Path(source).is_file():
        text = Path(source).read_text(encoding="utf-8-sig")
    else:
        raise AnswerKeyError(f"ไม่พบไฟล์เฉลย: {source}")
    reader = csv.DictReader(io.StringIO(text))
    fields = [f.strip().lower() for f in (reader.fieldnames or [])]
    if "question" not in fields or "answer" not in fields:
        raise AnswerKeyError("ไฟล์เฉลยต้องมีคอลัมน์ question และ answer")
    key: AnswerKey = {}
    for raw in reader:
        row = {k.strip().lower(): (v or "").strip() for k, v in raw.items() if k}
        if not row.get("question"):
            continue
        try:
            q = int(row["question"])
        except ValueError as exc:
            raise AnswerKeyError(f"เลขข้อไม่ถูกต้อง: {row['question']}") from exc
        ans = row.get("answer", "").upper()
        if not ans:
            continue
        if ans not in C.CHOICES:
            raise AnswerKeyError(f"ข้อ {q}: เฉลยต้องเป็น {'/'.join(C.CHOICES)} (พบ '{ans}')")
        if not 1 <= q <= C.MAX_QUESTIONS:
            raise AnswerKeyError(f"เลขข้อ {q} อยู่นอกช่วง 1–{C.MAX_QUESTIONS}")
        key[q] = ans
    if not key:
        raise AnswerKeyError("ไฟล์เฉลยไม่มีข้อมูล")
    return key


def answer_key_to_csv(key: AnswerKey) -> str:
    """แปลงเฉลยเป็นข้อความ CSV"""
    lines = ["question,answer"] + [f"{q},{a}" for q, a in sorted(key.items())]
    return "\n".join(lines) + "\n"


def grade(
    read_results: dict[int, ReadResult],
    answer_key: AnswerKey,
    sheet: SheetResult | None = None,
) -> SheetResult:
    """ให้คะแนน: ถูกเมื่อสถานะ OK/FAINT และคำตอบตรงเฉลย, MULTI/BLANK ได้ 0, ข้อที่ไม่มีเฉลยไม่นับ

    ข้อที่ YOLOv8n/ตรวจคุณภาพภาพพบปัญหาจะถูกทำเครื่องหมายไม่มั่นใจ (ยกเว้นข้อที่ผู้ตรวจแก้แล้ว)
    """
    sheet = sheet or SheetResult(filename="")
    previous = {p.number: p for p in sheet.questions}
    problems = sheet.problem_questions
    questions: list[QuestionResult] = []
    for q in sorted(read_results):
        if q not in answer_key:
            continue
        rr = read_results[q]
        correct = rr.status in (STATUS_OK, STATUS_FAINT) and rr.answer == answer_key[q]
        edited = previous[q].edited if q in previous else False
        problem = problems.get(q, "")
        questions.append(
            QuestionResult(
                number=q, answer=rr.answer, key=answer_key[q], status=rr.status, is_correct=correct,
                confidence=rr.confidence, uncertain=rr.uncertain or (bool(problem) and not edited),
                ratios=rr.ratios, edited=edited, problem=problem,
            )
        )
    sheet.questions = questions
    sheet.score = sum(q.is_correct for q in questions)
    sheet.total = len(questions)
    sheet.percent = round(100.0 * sheet.score / sheet.total, 2) if sheet.total else 0.0
    sheet.avg_confidence = round(sum(q.confidence for q in questions) / len(questions), 4) if questions else 0.0
    sheet.n_uncertain = sum(q.uncertain for q in questions)
    sheet.n_blank = sum(q.status == STATUS_BLANK for q in questions)
    sheet.n_multi = sum(q.status == STATUS_MULTI for q in questions)
    return sheet


def manual_read(answer: str) -> ReadResult:
    """สร้างผลอ่านจากการแก้ไขของผู้ตรวจ (ความมั่นใจ 100%)"""
    answer = "".join(ch for ch in C.CHOICES if ch in answer.upper())
    if not answer:
        status = STATUS_BLANK
    elif len(answer) > 1:
        status = STATUS_MULTI
    else:
        status = STATUS_OK
    return ReadResult(answer=answer, status=status, confidence=1.0, uncertain=False, ratios={})
