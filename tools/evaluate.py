"""วัด accuracy และเวลาประมวลผลเทียบกับ ground truth

ทุกครั้งที่รัน จะเพิ่มแถวลง reports/history.csv (เวอร์ชัน + จำนวนความผิดพลาด) แล้วเทียบกับเวอร์ชันก่อนหน้า
เพื่อหา "เวอร์ชันที่ดีที่สุด" (ดู CHANGELOG.md)

ตัวอย่าง:
    python tools/evaluate.py --images samples/synthetic --truth samples/synthetic/ground_truth.csv
    python tools/evaluate.py --images samples/synthetic --truth samples/synthetic/ground_truth.csv --note "ลองปรับ C=22"
    python tools/evaluate.py --real --images my_photos --truth my_photos/ground_truth.csv --key my_photos/key.csv
    python tools/evaluate.py --history          # ดูประวัติทุกเวอร์ชันโดยไม่ต้องรันใหม่
"""

from __future__ import annotations

import argparse
import csv
import logging
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import cv2  # noqa: E402
import numpy as np  # noqa: E402

from omr import __version__  # noqa: E402
from omr import config as C  # noqa: E402
from omr.grader import AnswerKey, parse_answer_key  # noqa: E402
from omr.pipeline import grade_image  # noqa: E402

KIND_NAMES = {"N": "ปกติ", "F": "ฝนจาง", "B": "ไม่ฝน", "M": "ฝนซ้ำ"}
HISTORY_FILE = "history.csv"
HISTORY_COLUMNS = ["version", "date", "mode", "images", "sheets", "detected", "q_total", "q_wrong", "q_wrong_silent",
                   "id_wrong", "id_wrong_silent", "flagged", "mean_ms", "p95_ms", "note"]
CONF_LABELS = [*C.CHOICES, "blank", "multi"]


def label_of(ans: str) -> str:
    """แปลงคำตอบเป็นหมวดของ confusion matrix"""
    if ans == "":
        return "blank"
    if len(ans) > 1:
        return "multi"
    return ans


def infer_kind(ans: str) -> str:
    """เดาประเภทจาก ground truth เมื่อไม่มีไฟล์ประเภท (ฝนจางแยกจากปกติไม่ได้)"""
    return "B" if ans == "" else "M" if len(ans) > 1 else "N"


@dataclass
class EvalStats:
    n_sheets: int = 0
    detected: int = 0
    q_total: int = 0
    q_correct: int = 0
    id_correct: int = 0
    sheet_correct: int = 0
    flagged: int = 0
    flagged_wrong: int = 0
    flagged_problem: int = 0  # ข้อที่ถูก flag จาก YOLOv8n/แสงสะท้อน
    id_wrong_silent: int = 0  # อ่านรหัสผิดแต่ระบบบอกว่าอ่านได้ครบ (ไม่เตือน)
    wrong_total: int = 0
    times: list[float] = field(default_factory=list)
    kind_total: Counter = field(default_factory=Counter)
    kind_correct: Counter = field(default_factory=Counter)
    confusion: dict[str, Counter] = field(default_factory=lambda: defaultdict(Counter))
    errors: list[dict[str, str]] = field(default_factory=list)


def pct(a: int, b: int) -> float:
    return 100.0 * a / b if b else 0.0


def evaluate(images: Path, truth_path: Path, key: AnswerKey | None, errors_dir: Path | None,
             kinds_path: Path | None) -> EvalStats:
    """ตรวจทุกภาพใน ground truth แล้วสรุปสถิติ"""
    truth = list(csv.DictReader(truth_path.open(encoding="utf-8-sig")))
    kinds: dict[str, dict[str, str]] = {}
    if kinds_path is not None and kinds_path.is_file():
        kinds = {r["filename"]: r for r in csv.DictReader(kinds_path.open(encoding="utf-8-sig"))}
    qcols = [c for c in truth[0].keys() if c.startswith("q") and c[1:].isdigit()] if truth else []
    key = key or {int(c[1:]): C.CHOICES[0] for c in qcols}
    st = EvalStats()

    for i, row in enumerate(truth, 1):
        path = images / row["filename"]
        res = grade_image(path, key, row["filename"], keep_images=errors_dir is not None)
        st.n_sheets += 1
        st.times.append(res.processing_ms)
        if res.error:
            st.errors.append({"filename": row["filename"], "question": "-", "truth": "", "read": "",
                              "status": "ERROR", "confidence": "", "note": res.error})
            print(f"[{i}/{len(truth)}] {row['filename']}: ERROR {res.error}")
            st.q_total += len(qcols)
            continue
        st.detected += 1
        id_ok = res.student_id == row["student_id"].zfill(C.STUDENT_ID_DIGITS)
        st.id_correct += id_ok
        if not id_ok and res.id_valid:
            st.id_wrong_silent += 1
        if not id_ok:
            st.errors.append({"filename": row["filename"], "question": "ID", "truth": row["student_id"],
                              "read": res.student_id, "status": "", "confidence": f"{res.id_confidence:.2f}",
                              "note": ""})
        n_wrong = 0
        graded = {qr.number: qr for qr in res.questions}  # มี flag จาก YOLO/แสงสะท้อนรวมอยู่ด้วย
        for col in qcols:
            q = int(col[1:])
            t = "".join(sorted(row[col].strip().upper()))
            rr = res.answer_reads.get(q)
            got = rr.answer if rr else ""
            kind = kinds.get(row["filename"], {}).get(col) or infer_kind(t)
            ok = got == t
            st.q_total += 1
            st.q_correct += ok
            st.kind_total[kind] += 1
            st.kind_correct[kind] += ok
            st.confusion[label_of(t)][label_of(got)] += 1
            qr = graded.get(q)
            if (qr.uncertain if qr else rr and rr.uncertain):
                st.flagged += 1
                st.flagged_wrong += not ok
            if qr and qr.problem:
                st.flagged_problem += 1
            if not ok:
                n_wrong += 1
                st.wrong_total += 1
                st.errors.append({"filename": row["filename"], "question": str(q), "truth": t, "read": got,
                                  "status": rr.status if rr else "", "note": KIND_NAMES.get(kind, kind),
                                  "confidence": f"{rr.confidence:.2f}" if rr else "",
                                  "ratios": " ".join(f"{k}={v:.2f}" for k, v in (rr.ratios if rr else {}).items())})
        st.sheet_correct += id_ok and n_wrong == 0
        if (n_wrong or not id_ok) and errors_dir is not None and res.annotated_image is not None:
            errors_dir.mkdir(parents=True, exist_ok=True)
            cv2.imwrite(str(errors_dir / f"{Path(row['filename']).stem}_annotated.jpg"), res.annotated_image)
        if i % 10 == 0 or i == len(truth):
            print(f"ตรวจแล้ว {i}/{len(truth)}")
    return st


def build_report(st: EvalStats, images: Path, real: bool) -> str:
    """สร้างรายงาน markdown"""
    t = np.array(st.times) if st.times else np.zeros(1)
    lines = [
        f"# ผลการประเมิน OMR ({'ภาพจริง' if real else 'ภาพสังเคราะห์'})",
        "",
        f"- เวอร์ชัน: {__version__}",
        f"- วันที่: {datetime.now():%Y-%m-%d %H:%M}",
        f"- โฟลเดอร์ภาพ: `{images}`",
        f"- ค่าเกณฑ์: FILL={C.FILL_THRESHOLD}, FAINT={C.FAINT_THRESHOLD}, "
        f"CONFIDENCE={C.CONFIDENCE_THRESHOLD}, SAMPLE_RATIO={C.BUBBLE_SAMPLE_RATIO}",
        "",
        "## สรุป",
        "",
        "| ตัวชี้วัด | ค่า |",
        "|---|---|",
        f"| จำนวนแผ่น | {st.n_sheets} |",
        f"| Detection rate | {pct(st.detected, st.n_sheets):.2f}% ({st.detected}/{st.n_sheets}) |",
        f"| Question accuracy | {pct(st.q_correct, st.q_total):.2f}% ({st.q_correct}/{st.q_total}) |",
        f"| Student ID accuracy | {pct(st.id_correct, st.n_sheets):.2f}% ({st.id_correct}/{st.n_sheets}) |",
        f"| Sheet accuracy | {pct(st.sheet_correct, st.n_sheets):.2f}% ({st.sheet_correct}/{st.n_sheets}) |",
        f"| Uncertain rate | {pct(st.flagged, st.q_total):.2f}% ({st.flagged}/{st.q_total}) |",
        f"| Uncertain precision (flag แล้วอ่านผิดจริง) | {pct(st.flagged_wrong, st.flagged):.2f}% "
        f"({st.flagged_wrong}/{st.flagged}) |",
        f"| ข้อที่ YOLOv8n/แสงสะท้อนพบปัญหา | {st.flagged_problem} |",
        f"| ข้อที่อ่านผิดถูก flag ไว้ (recall) | {pct(st.flagged_wrong, st.wrong_total):.2f}% "
        f"({st.flagged_wrong}/{st.wrong_total}) |",
        f"| **ความผิดพลาดที่ไม่มีการเตือน** (ข้อ + รหัส + แผ่นที่หาไม่เจอ) | "
        f"**{st.wrong_total - st.flagged_wrong + st.id_wrong_silent + st.n_sheets - st.detected}** |",
        f"| เวลาเฉลี่ย/แผ่น | {t.mean():.1f} ms |",
        f"| เวลา p95/แผ่น | {np.percentile(t, 95):.1f} ms |",
        f"| เวลาสูงสุด/แผ่น | {t.max():.1f} ms |",
        "",
        "## Accuracy แยกตามประเภท",
        "",
        "| ประเภท | ถูก/ทั้งหมด | Accuracy |",
        "|---|---|---|",
    ]
    for k in ("N", "F", "B", "M"):
        if st.kind_total[k]:
            lines.append(f"| {KIND_NAMES[k]} | {st.kind_correct[k]}/{st.kind_total[k]} | "
                         f"{pct(st.kind_correct[k], st.kind_total[k]):.2f}% |")
    lines += ["", "## Confusion matrix (แถว = ground truth, คอลัมน์ = อ่านได้)", "",
              "| truth \\ read | " + " | ".join(CONF_LABELS) + " |", "|---" * (len(CONF_LABELS) + 1) + "|"]
    for a in CONF_LABELS:
        lines.append(f"| {a} | " + " | ".join(str(st.confusion[a][b]) for b in CONF_LABELS) + " |")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# ประวัติเวอร์ชัน: นับความผิดพลาดแต่ละเวอร์ชัน แล้วเลือกเวอร์ชันที่ดีที่สุด
# ---------------------------------------------------------------------------
def history_row(st: EvalStats, images: Path, real: bool, note: str) -> dict[str, str]:
    t = np.array(st.times) if st.times else np.zeros(1)
    return {
        "version": __version__, "date": f"{datetime.now():%Y-%m-%d %H:%M}", "mode": "real" if real else "synthetic",
        "images": images.name, "sheets": str(st.n_sheets), "detected": str(st.detected), "q_total": str(st.q_total),
        "q_wrong": str(st.wrong_total), "q_wrong_silent": str(st.wrong_total - st.flagged_wrong),
        "id_wrong": str(st.n_sheets - st.id_correct), "id_wrong_silent": str(st.id_wrong_silent),
        "flagged": str(st.flagged), "mean_ms": f"{t.mean():.1f}", "p95_ms": f"{np.percentile(t, 95):.1f}",
        "note": note,
    }


def load_history(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def append_history(path: Path, row: dict[str, str]) -> None:
    new = not path.is_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8-sig" if new else "utf-8", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=HISTORY_COLUMNS)
        if new:
            wr.writeheader()
        wr.writerow({c: row.get(c, "") for c in HISTORY_COLUMNS})


def _num(row: dict[str, str], col: str, default: float) -> float:
    try:
        return float(row.get(col) or default)
    except ValueError:
        return default


def total_errors(row: dict[str, str]) -> int:
    """ความผิดพลาดทั้งหมด = ข้อที่อ่านผิด + รหัสที่อ่านผิด + แผ่นที่หามาร์กเกอร์ไม่เจอ"""
    missed = _num(row, "sheets", 0) - _num(row, "detected", 0)
    return int(_num(row, "q_wrong", 0) + _num(row, "id_wrong", 0) + missed)


def silent_errors(row: dict[str, str]) -> int:
    """ความผิดพลาดที่ระบบไม่เตือนผู้ตรวจ (อันตรายที่สุด) — ถ้าไม่มีข้อมูลถือว่าไม่เตือนทั้งหมด"""
    missed = _num(row, "sheets", 0) - _num(row, "detected", 0)
    q_silent = _num(row, "q_wrong_silent", _num(row, "q_wrong", 0))
    id_silent = _num(row, "id_wrong_silent", _num(row, "id_wrong", 0))
    return int(q_silent + id_silent + missed)


def rank_key(row: dict[str, str]) -> tuple[float, ...]:
    """เกณฑ์เลือกเวอร์ชันที่ดีที่สุด: ผิดโดยไม่เตือนน้อยสุด → ผิดรวมน้อยสุด → เตือนน้อยสุด (ผู้ตรวจทำงานน้อย) → เร็วสุด"""
    return (silent_errors(row), total_errors(row), _num(row, "flagged", float("inf")),
            _num(row, "mean_ms", float("inf")))


def best_row(rows: list[dict[str, str]]) -> dict[str, str] | None:
    return min(rows, key=rank_key) if rows else None


def history_table(rows: list[dict[str, str]]) -> str:
    """ตารางเทียบทุกเวอร์ชันในชุดข้อมูลเดียวกัน ★ = เวอร์ชันที่ดีที่สุด"""
    best = best_row(rows)
    lines = ["| | เวอร์ชัน | วันที่ | ผิดรวม | ผิดโดยไม่เตือน | ข้อผิด | รหัสผิด | แผ่นหาไม่เจอ | ข้อที่เตือน | เวลาเฉลี่ย (ms) | หมายเหตุ |",
             "|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        missed = int(_num(r, "sheets", 0) - _num(r, "detected", 0))
        lines.append(
            f"| {'★' if r is best else ''} | {r['version']} | {r['date']} | {total_errors(r)} | {silent_errors(r)} | "
            f"{r['q_wrong']}/{r['q_total']} | {r['id_wrong']} | {missed} | {r.get('flagged') or '-'} | "
            f"{r.get('mean_ms') or '-'} | {r.get('note', '')} |")
    return "\n".join(lines)


def print_history(path: Path, mode: str | None = None, images: str | None = None) -> None:
    rows = [r for r in load_history(path)
            if (mode is None or r["mode"] == mode) and (images is None or r["images"] == images)]
    if not rows:
        print("ยังไม่มีประวัติ")
        return
    for key in sorted({(r["mode"], r["images"]) for r in rows}):
        group = [r for r in rows if (r["mode"], r["images"]) == key]
        best = best_row(group)
        print(f"\n## ชุดข้อมูล {key[1]} ({key[0]}) — เวอร์ชันที่ดีที่สุด: {best['version']} ({best['date']})\n")
        print(history_table(group))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="วัด accuracy ของระบบ OMR")
    parser.add_argument("--images", help="โฟลเดอร์ภาพ")
    parser.add_argument("--truth", help="ground_truth.csv (filename,student_id,q1..qN)")
    parser.add_argument("--key", default="", help="เฉลย CSV (ถ้าไม่ระบุใช้ answer_key.csv ในโฟลเดอร์ภาพ)")
    parser.add_argument("--kinds", default="", help="ไฟล์ประเภทรายข้อ (ค่าเริ่มต้น ground_truth_kinds.csv)")
    parser.add_argument("--real", action="store_true", help="โหมดภาพถ่ายจริงที่ผู้ใช้เตรียมเอง")
    parser.add_argument("--reports", default=str(C.REPORTS_DIR))
    parser.add_argument("--note", default="", help="บันทึกสั้น ๆ ว่ารอบนี้ปรับอะไร (เก็บใน history.csv)")
    parser.add_argument("--history", action="store_true", help="แสดงประวัติทุกเวอร์ชันแล้วจบ (ไม่รันใหม่)")
    parser.add_argument("--no-history", action="store_true", help="ไม่บันทึกลง history.csv (เช่น ทดลองชั่วคราว)")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.ERROR)
    history_path = Path(args.reports) / HISTORY_FILE
    if args.history:
        print_history(history_path)
        return 0
    if not args.images or not args.truth:
        parser.error("ต้องระบุ --images และ --truth (หรือใช้ --history)")

    images, truth = Path(args.images), Path(args.truth)
    key_path = Path(args.key) if args.key else images / "answer_key.csv"
    key = parse_answer_key(key_path) if key_path.is_file() else None
    kinds_path = Path(args.kinds) if args.kinds else truth.with_name("ground_truth_kinds.csv")
    reports = Path(args.reports)
    stamp = f"{datetime.now():%Y%m%d_%H%M}"
    prefix = "eval_real" if args.real else "eval"
    errors_dir = reports / ("errors_real" if args.real else "errors")

    st = evaluate(images, truth, key, errors_dir, None if args.real and not args.kinds else kinds_path)
    report = build_report(st, images, args.real)
    reports.mkdir(parents=True, exist_ok=True)
    (reports / f"{prefix}_{stamp}.md").write_text(report, encoding="utf-8")
    err_csv = reports / f"{prefix}_{stamp}_errors.csv"
    with err_csv.open("w", newline="", encoding="utf-8-sig") as f:
        cols = ["filename", "question", "truth", "read", "status", "confidence", "ratios", "note"]
        wr = csv.DictWriter(f, fieldnames=cols)
        wr.writeheader()
        for e in st.errors:
            wr.writerow({c: e.get(c, "") for c in cols})
    print()
    print(report)
    print(f"บันทึกรายงาน: {reports / f'{prefix}_{stamp}.md'}")
    print(f"รายการข้อที่อ่านผิด: {err_csv}")
    if not args.no_history:
        row = history_row(st, images, args.real, args.note)
        append_history(history_path, row)
        print_history(history_path, row["mode"], row["images"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
