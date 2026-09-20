"""ตรวจข้อสอบและสร้างกระดาษคำตอบจาก command line

ตัวอย่าง:
    python tools/cli.py sheet --out samples/answer_sheet.pdf
    python tools/cli.py grade samples/synthetic --key samples/synthetic/answer_key.csv --out results.xlsx
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import cv2  # noqa: E402

from omr import config as C  # noqa: E402
from omr.exporter import export_excel  # noqa: E402
from omr.grader import parse_answer_key  # noqa: E402
from omr.pipeline import grade_image  # noqa: E402
from omr.sheet_generator import save_sheets  # noqa: E402


def collect_images(target: Path) -> list[Path]:
    """รวบรวมไฟล์ภาพจากไฟล์เดียวหรือโฟลเดอร์"""
    if target.is_file():
        return [target]
    exts = C.SUPPORTED_EXTENSIONS + C.UNSUPPORTED_HINT_EXTENSIONS
    return sorted(p for p in target.iterdir() if p.suffix.lower() in exts)


def cmd_grade(args: argparse.Namespace) -> int:
    key = parse_answer_key(Path(args.key))
    images = collect_images(Path(args.target))
    if not images:
        print(f"ไม่พบไฟล์ภาพใน {args.target}")
        return 1
    ann_dir = Path(args.annotated) if args.annotated else None
    results = []
    for i, path in enumerate(images, 1):
        r = grade_image(path, key, path.name, debug=args.debug, keep_images=ann_dir is not None)
        results.append(r)
        if r.error:
            print(f"[{i}/{len(images)}] {path.name}: ผิดพลาด — {r.error}")
        else:
            flag = " (ต้องตรวจสอบ)" if r.needs_review else ""
            print(f"[{i}/{len(images)}] {path.name}: รหัส {r.student_id} คะแนน {r.score}/{r.total} "
                  f"({r.processing_ms:.0f} ms){flag}")
        if ann_dir is not None and r.annotated_image is not None:
            ann_dir.mkdir(parents=True, exist_ok=True)
            cv2.imwrite(str(ann_dir / f"{path.stem}_annotated.jpg"), r.annotated_image)
        r.warped_image = r.original_preview = r.annotated_image = None  # ลดหน่วยความจำ
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(export_excel(results, key))
    ok = sum(r.error is None for r in results)
    print(f"ตรวจสำเร็จ {ok}/{len(results)} แผ่น → บันทึก {out}")
    return 0


def cmd_sheet(args: argparse.Namespace) -> int:
    out = Path(args.out)
    png = Path(args.png) if args.png else out.with_suffix(".png")
    save_sheets(out, png, args.questions)
    print(f"บันทึก {out} และ {png}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="OMR Grading CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    g = sub.add_parser("grade", help="ตรวจภาพหรือโฟลเดอร์ภาพ")
    g.add_argument("target", help="ไฟล์ภาพหรือโฟลเดอร์")
    g.add_argument("--key", required=True, help="ไฟล์เฉลย CSV (question,answer)")
    g.add_argument("--out", default="results.xlsx", help="ไฟล์ Excel ผลลัพธ์")
    g.add_argument("--annotated", default="", help="โฟลเดอร์บันทึกภาพ annotate (ไม่บังคับ)")
    g.add_argument("--debug", action="store_true", help="บันทึกภาพระหว่างขั้นตอนลง debug/")
    g.set_defaults(func=cmd_grade)

    s = sub.add_parser("sheet", help="สร้างกระดาษคำตอบ PDF + PNG")
    s.add_argument("--out", default=str(C.SAMPLES_DIR / "answer_sheet.pdf"))
    s.add_argument("--png", default="", help="path ของ PNG (ค่าเริ่มต้น: ชื่อเดียวกับ PDF)")
    s.add_argument("--questions", type=int, default=C.NUM_QUESTIONS)
    s.set_defaults(func=cmd_sheet)

    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
