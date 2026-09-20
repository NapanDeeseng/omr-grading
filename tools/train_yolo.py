"""สร้างชุดข้อมูลสังเคราะห์ (label อัตโนมัติ) แล้วเทรน YOLOv8n ให้ตรวจจับบริเวณที่มีปัญหาบนกระดาษคำตอบ

คลาส: multi_mark (ทั้งแถวที่ฝนหลายตัวเลือก), faint_mark (bubble ที่ฝนจาง), erasure (bubble ที่มีรอยลบ)
ภาพ train = พื้นที่คำตอบที่ครอปจากภาพหลัง warp ด้วย pipeline จริง จึงตรงกับภาพตอนใช้งาน

ตัวอย่าง:
    python tools/train_yolo.py                          # สร้างข้อมูล + เทรน + คัดลอกโมเดลไป models/
    python tools/train_yolo.py --n-train 400 --epochs 60
    python tools/train_yolo.py --skip-generate          # เทรนต่อจากชุดข้อมูลเดิม
"""

from __future__ import annotations

import argparse
import logging
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import cv2  # noqa: E402
import numpy as np  # noqa: E402

import synth  # noqa: E402
from omr import config as C  # noqa: E402
from omr import layout as L  # noqa: E402
from omr import preprocess  # noqa: E402
from omr.errors import OMRError  # noqa: E402
from omr.pipeline import align_sheet  # noqa: E402
from omr.sheet_generator import generate_png_image  # noqa: E402

log = logging.getLogger("train_yolo")

DATASET_DIR = C.PROJECT_ROOT / "datasets" / "omr_problems"
RUNS_DIR = C.PROJECT_ROOT / "runs"
BOX_PAD = 1.6            # ขนาดกรอบ = รัศมี bubble × ค่านี้ (ครอบรอยฝนที่เลยขอบ)
# เพิ่มความถี่ของกรณีที่มีปัญหาให้โมเดลเห็นตัวอย่างมากพอ (ภาพจริงมีไม่ถึง 5%)
TRAIN_P_FAINT, TRAIN_P_MULTI, TRAIN_P_ERASE_SHEET = 0.08, 0.08, 0.85


def _bubble_box(x: float, y: float, r: float) -> tuple[float, float, float, float]:
    return x - BOX_PAD * r, y - BOX_PAD * r, x + BOX_PAD * r, y + BOX_PAD * r


def sheet_labels(answers: dict[int, str], kinds: dict[int, str], erasures: list[tuple[float, float, float]],
                 num_q: int) -> list[tuple[int, tuple[float, float, float, float]]]:
    """label ในพิกัดภาพหลัง warp: [(class_id, (x0, y0, x1, y1))]"""
    bubbles = L.answer_bubbles_px(num_q)
    cls = {name: i for i, name in enumerate(C.YOLO_CLASSES)}
    out = []
    for q, kind in kinds.items():
        row = bubbles[q]
        if kind == "M":
            boxes = [_bubble_box(*row[ch]) for ch in row]
            out.append((cls["multi_mark"], (min(b[0] for b in boxes), min(b[1] for b in boxes),
                                            max(b[2] for b in boxes), max(b[3] for b in boxes))))
        elif kind == "F":
            out.append((cls["faint_mark"], _bubble_box(*row[answers[q]])))
    answer_y0 = L.answer_region_px(num_q)[1]
    for x, y, r in erasures:
        if y > answer_y0:  # รอยลบในบล็อกรหัสไม่อยู่ในภาพครอป
            out.append((cls["erasure"], _bubble_box(x, y, r)))
    return out


def to_yolo_lines(labels: list[tuple[int, tuple[float, float, float, float]]],
                  region: tuple[int, int, int, int]) -> list[str]:
    """แปลงเป็นรูปแบบ YOLO (class cx cy w h แบบ normalize) เทียบกับภาพครอป"""
    rx0, ry0, rx1, ry1 = region
    w, h = rx1 - rx0, ry1 - ry0
    lines = []
    for c, (x0, y0, x1, y1) in labels:
        x0, x1 = np.clip([x0 - rx0, x1 - rx0], 0, w)
        y0, y1 = np.clip([y0 - ry0, y1 - ry0], 0, h)
        if x1 - x0 < 2 or y1 - y0 < 2:
            continue
        lines.append(f"{c} {(x0 + x1) / 2 / w:.6f} {(y0 + y1) / 2 / h:.6f} {(x1 - x0) / w:.6f} {(y1 - y0) / h:.6f}")
    return lines


def generate(out: Path, n_train: int, n_val: int, seed: int, num_q: int) -> None:
    """สร้างภาพสังเคราะห์ → warp ด้วย pipeline → ครอปพื้นที่คำตอบ → บันทึกภาพ + label"""
    synth.P_FAINT, synth.P_MULTI, synth.P_ERASE_SHEET = TRAIN_P_FAINT, TRAIN_P_MULTI, TRAIN_P_ERASE_SHEET
    synth.P_NORMAL = 1.0 - synth.P_FAINT - synth.P_BLANK - synth.P_MULTI
    rng = np.random.default_rng(seed)
    base = generate_png_image(num_q)
    region = L.answer_region_px(num_q)
    if out.exists():
        shutil.rmtree(out)
    counts = np.zeros(len(C.YOLO_CLASSES), int)
    for split, n in (("train", n_train), ("val", n_val)):
        (out / "images" / split).mkdir(parents=True)
        (out / "labels" / split).mkdir(parents=True)
        done = 0
        while done < n:
            erasures: list[tuple[float, float, float]] = []
            img, _, answers, kinds = synth.synth_one(rng, base, num_q, erasures)
            quality = int(rng.integers(*synth.JPEG_QUALITY))
            img = cv2.imdecode(cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, quality])[1], cv2.IMREAD_COLOR)
            try:
                warped, _ = align_sheet(img)
            except OMRError:
                continue
            warped, _ = preprocess.fix_orientation(warped)
            x0, y0, x1, y1 = region
            labels = sheet_labels(answers, kinds, erasures, num_q)
            for c, _ in labels:
                counts[c] += 1
            name = f"{split}_{done:04d}"
            cv2.imwrite(str(out / "images" / split / f"{name}.jpg"), warped[y0:y1, x0:x1])
            (out / "labels" / split / f"{name}.txt").write_text("\n".join(to_yolo_lines(labels, region)) + "\n")
            done += 1
            if done % 50 == 0 or done == n:
                log.info("%s: %d/%d", split, done, n)
    names = "\n".join(f"  {i}: {n}" for i, n in enumerate(C.YOLO_CLASSES))
    (out / "data.yaml").write_text(f"path: {out.as_posix()}\ntrain: images/train\nval: images/val\nnames:\n{names}\n",
                                   encoding="utf-8")
    log.info("จำนวนกรอบต่อคลาส: %s", dict(zip(C.YOLO_CLASSES, counts.tolist())))


def train(data: Path, epochs: int, imgsz: int, batch: int, base_model: str) -> Path:
    """เทรน YOLOv8n แล้วคืน path ของ best.pt"""
    from ultralytics import YOLO

    try:
        model = YOLO(base_model)  # yolov8n.pt = pretrained COCO (ถ้าไม่มีไฟล์ ultralytics ดาวน์โหลดให้)
    except Exception as exc:  # noqa: BLE001 — ไม่มีอินเทอร์เน็ตให้เริ่มจากศูนย์
        log.warning("โหลด %s ไม่ได้ (%s) เริ่มเทรนจากศูนย์ด้วย yolov8n.yaml", base_model, exc)
        model = YOLO("yolov8n.yaml")
    model.train(
        data=str(data), epochs=epochs, imgsz=imgsz, batch=batch, device="cpu", workers=0,
        project=str(RUNS_DIR), name="omr_problems", exist_ok=True, plots=False,
        # ตำแหน่งแถว/คอลัมน์ไม่มีความหมายต่อคลาส จึงพลิกซ้ายขวาได้ แต่ไม่หมุน/ไม่ mosaic เพื่อคงขนาดวัตถุ
        fliplr=0.5, flipud=0.0, mosaic=0.0, degrees=0.0, scale=0.2, translate=0.05,
        hsv_h=0.0, hsv_s=0.2, hsv_v=0.3, patience=10,
    )
    return Path(model.trainer.best)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="เทรน YOLOv8n ตรวจจับบริเวณที่มีปัญหาบนกระดาษคำตอบ")
    parser.add_argument("--out", default=str(DATASET_DIR))
    parser.add_argument("--n-train", type=int, default=250)
    parser.add_argument("--n-val", type=int, default=50)
    parser.add_argument("--seed", type=int, default=2024)
    parser.add_argument("--questions", type=int, default=C.NUM_QUESTIONS)
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--imgsz", type=int, default=C.YOLO_IMGSZ)
    parser.add_argument("--batch", type=int, default=8)
    parser.add_argument("--model", default=str(C.MODELS_DIR / "yolov8n.pt"))
    parser.add_argument("--skip-generate", action="store_true")
    parser.add_argument("--generate-only", action="store_true")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    out = Path(args.out)
    if not args.skip_generate:
        generate(out, args.n_train, args.n_val, args.seed, args.questions)
    if args.generate_only:
        return 0
    best = train(out / "data.yaml", args.epochs, args.imgsz, args.batch, args.model)
    C.MODELS_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(best, C.YOLO_WEIGHTS)
    log.info("บันทึกโมเดลที่ %s", C.YOLO_WEIGHTS)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
