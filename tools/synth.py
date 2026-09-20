"""สร้างภาพถ่ายกระดาษคำตอบสังเคราะห์ + ground truth สำหรับทดสอบ

ตัวอย่าง:
    python tools/synth.py --n 100 --out samples/synthetic --seed 42
"""

from __future__ import annotations

import argparse
import csv
import logging
import math
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import cv2  # noqa: E402
import numpy as np  # noqa: E402

from omr import config as C  # noqa: E402
from omr import layout as L  # noqa: E402
from omr.sheet_generator import generate_png_image  # noqa: E402

log = logging.getLogger("synth")

# ---------------------------------------------------------------------------
# พารามิเตอร์การสุ่ม (ตาม spec)
# ---------------------------------------------------------------------------
OUT_W, OUT_H = 1536, 2048                 # ขนาดภาพแบบกล้องมือถือ 3:4
P_NORMAL, P_FAINT, P_BLANK, P_MULTI = 0.88, 0.04, 0.04, 0.04
FILL_SIZE = (0.80, 1.10)                  # ขนาดวงรีเทียบ bubble
OVERSHOOT_SIZE = (1.10, 1.25)             # แผ่นที่ฝนเลยขอบ
P_OVERSHOOT_SHEET = 0.25
FILL_OFFSET_SIGMA = 0.08                  # เลื่อนตำแหน่ง (สัดส่วนรัศมี)
NORMAL_INTENSITY = (60, 95)
FAINT_INTENSITY = (150, 190)
PENCIL_TEXTURE_SIGMA = 14.0
P_ERASE_SHEET = 0.35
ERASE_COUNT = (1, 4)
ERASE_INTENSITY = (195, 225)
ERASE_ALPHA = (0.4, 0.8)
PAPER_TONE = (232, 252)
ROTATION_DEG = 15.0
KEYSTONE = 0.035
PAPER_SCALE = (0.60, 0.95)
P_UPSIDE_DOWN = 0.10
FIT_MARGIN = 0.98
GRADIENT_MIN = (0.65, 0.95)
P_PARTIAL_SHADOW = 0.5
PARTIAL_SHADOW = (0.55, 0.85)
BRIGHTNESS = (-25, 25)
CONTRAST = (0.75, 1.15)
COLOR_CAST = (0.90, 1.10)
NOISE_SIGMA = (2.0, 8.0)
BLUR_SIGMA = (0.0, 2.0)
JPEG_QUALITY = (60, 90)


@dataclass
class SheetTruth:
    filename: str
    student_id: str
    answers: dict[int, str]
    kinds: dict[int, str]  # N=ปกติ F=จาง B=ไม่ฝน M=ฝนซ้ำ


def pencil_mark(gray: np.ndarray, x: float, y: float, r: float, rng: np.random.Generator,
                intensity: tuple[float, float], size: tuple[float, float], alpha: float = 1.0) -> None:
    """ฝนวงรีทึบแบบดินสอพร้อม texture ลงภาพ grayscale (float32) แบบ in-place"""
    ax, ay = r * rng.uniform(*size), r * rng.uniform(*size)
    cx = x + rng.normal(0, FILL_OFFSET_SIGMA * r)
    cy = y + rng.normal(0, FILL_OFFSET_SIGMA * r)
    half = int(math.ceil(max(ax, ay) + 3))
    x0, y0 = int(cx) - half, int(cy) - half
    size_px = 2 * half + 1
    mask = np.zeros((size_px, size_px), np.float32)
    cv2.ellipse(mask, (half + int(round(cx - int(cx))), half + int(round(cy - int(cy)))),
                (int(round(ax)), int(round(ay))), float(rng.uniform(0, 180)), 0, 360, 1.0, -1, cv2.LINE_AA)
    mask = cv2.GaussianBlur(mask, (3, 3), 0) * alpha
    # เส้นดินสอ: noise ยืดตามแนวลากเพื่อให้ดูเป็นลายขีด
    tex = rng.normal(0, PENCIL_TEXTURE_SIGMA, (size_px, size_px)).astype(np.float32)
    tex = cv2.blur(tex, (5, 1))
    value = rng.uniform(*intensity) + tex
    patch = gray[y0: y0 + size_px, x0: x0 + size_px]
    if patch.shape != mask.shape:
        return
    dark = np.minimum(patch, value)
    patch[:] = patch * (1 - mask) + dark * mask


def random_sheet(rng: np.random.Generator, base: np.ndarray, num_q: int,
                 erasures: list[tuple[float, float, float]] | None = None,
                 ) -> tuple[np.ndarray, str, dict[int, str], dict[int, str]]:
    """ฝนคำตอบและรหัสแบบสุ่มลงกระดาษ คืน (ภาพ gray float, รหัส, คำตอบ, ประเภท)

    ถ้าส่ง list ``erasures`` มา จะเพิ่มพิกัด bubble (x, y, r) ที่มีรอยลบลงไป (ใช้สร้าง label ให้ YOLO)
    """
    gray = cv2.cvtColor(base, cv2.COLOR_BGR2GRAY).astype(np.float32)
    gray = np.minimum(gray, rng.uniform(*PAPER_TONE))
    overshoot = rng.random() < P_OVERSHOOT_SHEET
    size = OVERSHOOT_SIZE if overshoot else FILL_SIZE
    used: set[tuple[float, float]] = set()

    sid = "".join(str(d) for d in rng.integers(0, 10, C.STUDENT_ID_DIGITS))
    for col, digit in zip(L.student_id_bubbles_px(), sid):
        x, y, r = col[int(digit)]
        pencil_mark(gray, x, y, r, rng, NORMAL_INTENSITY, size)
        used.add((x, y))

    answers: dict[int, str] = {}
    kinds: dict[int, str] = {}
    bubbles = L.answer_bubbles_px(num_q)
    for q, row in bubbles.items():
        u = rng.random()
        choices = list(C.CHOICES)
        if u < P_NORMAL:
            ch = str(rng.choice(choices))
            pencil_mark(gray, *row[ch], rng, NORMAL_INTENSITY, size)
            answers[q], kinds[q] = ch, "N"
            used.add(row[ch][:2])
        elif u < P_NORMAL + P_FAINT:
            ch = str(rng.choice(choices))
            pencil_mark(gray, *row[ch], rng, FAINT_INTENSITY, FILL_SIZE)
            answers[q], kinds[q] = ch, "F"
            used.add(row[ch][:2])
        elif u < P_NORMAL + P_FAINT + P_BLANK:
            answers[q], kinds[q] = "", "B"
        else:
            picks = sorted(rng.choice(choices, 2, replace=False).tolist())
            for ch in picks:
                pencil_mark(gray, *row[ch], rng, NORMAL_INTENSITY, size)
                used.add(row[ch][:2])
            answers[q], kinds[q] = "".join(picks), "M"

    # รอยลบจาง ๆ ใน bubble ที่ไม่ได้ฝน
    if rng.random() < P_ERASE_SHEET:
        free = [b for row in bubbles.values() for b in row.values() if b[:2] not in used]
        for idx in rng.choice(len(free), int(rng.integers(*ERASE_COUNT)), replace=False):
            pencil_mark(gray, *free[idx], rng, ERASE_INTENSITY, FILL_SIZE, alpha=float(rng.uniform(*ERASE_ALPHA)))
            if erasures is not None:
                erasures.append(free[idx])
    return gray, sid, answers, kinds


def make_background(rng: np.random.Generator) -> np.ndarray:
    """พื้นหลังสุ่ม: ลายไม้ / สีเรียบ / noise"""
    kind = rng.integers(0, 3)
    yy, xx = np.mgrid[0:OUT_H, 0:OUT_W].astype(np.float32)
    if kind == 0:  # ลายไม้
        base = np.array([rng.uniform(30, 70), rng.uniform(60, 110), rng.uniform(100, 170)], np.float32)
        warp_noise = cv2.resize(rng.normal(0, 1, (OUT_H // 64, OUT_W // 64)).astype(np.float32), (OUT_W, OUT_H))
        freq = rng.uniform(0.02, 0.06)
        stripes = np.sin((xx * math.sin(0.2) + yy) * freq + warp_noise * 3.0)
        bg = base[None, None, :] * (0.8 + 0.2 * stripes[..., None])
    elif kind == 1:  # สีเรียบ
        bg = np.ones((OUT_H, OUT_W, 3), np.float32) * rng.uniform(20, 220, 3).astype(np.float32)
    else:  # noise
        n = cv2.resize(rng.normal(0, 1, (OUT_H // 16, OUT_W // 16, 3)).astype(np.float32), (OUT_W, OUT_H))
        bg = rng.uniform(40, 160, 3).astype(np.float32) + n * rng.uniform(15, 40)
    bg += rng.normal(0, 6, bg.shape).astype(np.float32)
    return np.clip(bg, 0, 255)


def random_homography(rng: np.random.Generator, w: int, h: int) -> tuple[np.ndarray, bool]:
    """สุ่ม perspective: หมุน ±15°, keystone, scale, กลับหัว 10%"""
    upside = bool(rng.random() < P_UPSIDE_DOWN)
    theta = math.radians(rng.uniform(-ROTATION_DEG, ROTATION_DEG) + (180.0 if upside else 0.0))
    scale = rng.uniform(*PAPER_SCALE) * OUT_H / h
    src = np.array([[0, 0], [w, 0], [w, h], [0, h]], np.float32)
    pts = (src - [w / 2, h / 2]) * scale
    pts += rng.uniform(-KEYSTONE, KEYSTONE, pts.shape) * [w * scale, h * scale]
    rot = np.array([[math.cos(theta), -math.sin(theta)], [math.sin(theta), math.cos(theta)]], np.float32)
    pts = pts @ rot.T
    span = pts.max(axis=0) - pts.min(axis=0)
    fit = min(1.0, FIT_MARGIN * OUT_W / span[0], FIT_MARGIN * OUT_H / span[1])
    pts *= fit
    lo, hi = pts.min(axis=0), pts.max(axis=0)
    room = np.array([OUT_W, OUT_H]) - (hi - lo)
    offset = -lo + rng.uniform(0.0, 1.0, 2) * np.maximum(room, 0)
    dst = (pts + offset).astype(np.float32)
    return cv2.getPerspectiveTransform(src, dst), upside


def apply_lighting(img: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """เงา gradient, เงาบางส่วน, ความสว่าง/contrast, color cast"""
    yy, xx = np.mgrid[0:OUT_H, 0:OUT_W].astype(np.float32)
    ang = rng.uniform(0, 2 * math.pi)
    proj = xx * math.cos(ang) + yy * math.sin(ang)
    proj = (proj - proj.min()) / (proj.max() - proj.min())
    low = rng.uniform(*GRADIENT_MIN)
    light = low + (1 - low) * proj
    if rng.random() < P_PARTIAL_SHADOW:
        ang2 = rng.uniform(0, 2 * math.pi)
        d = (xx - rng.uniform(0, OUT_W)) * math.cos(ang2) + (yy - rng.uniform(0, OUT_H)) * math.sin(ang2)
        soft = rng.uniform(20, 120)
        edge = 1.0 / (1.0 + np.exp(np.clip(-d / soft, -50.0, 50.0)))
        light *= 1.0 - (1.0 - rng.uniform(*PARTIAL_SHADOW)) * edge
    out = img * light[..., None]
    out = out * rng.uniform(*CONTRAST) + rng.uniform(*BRIGHTNESS)
    out *= rng.uniform(*COLOR_CAST, 3).astype(np.float32)
    return out


def synth_one(rng: np.random.Generator, base: np.ndarray, num_q: int,
              erasures: list[tuple[float, float, float]] | None = None,
              ) -> tuple[np.ndarray, str, dict[int, str], dict[int, str]]:
    """สร้างภาพหนึ่งแผ่น คืน (ภาพ BGR uint8 ก่อนบีบอัด, รหัส, คำตอบ, ประเภท)"""
    gray, sid, answers, kinds = random_sheet(rng, base, num_q, erasures)
    h, w = gray.shape
    paper = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
    matrix, _ = random_homography(rng, w, h)
    warped = cv2.warpPerspective(paper, matrix, (OUT_W, OUT_H), flags=cv2.INTER_LINEAR)
    mask = cv2.warpPerspective(np.ones((h, w), np.float32), matrix, (OUT_W, OUT_H), flags=cv2.INTER_LINEAR)
    bg = make_background(rng)
    img = warped * mask[..., None] + bg * (1 - mask[..., None])
    img = apply_lighting(img, rng)
    img += rng.normal(0, rng.uniform(*NOISE_SIGMA), img.shape).astype(np.float32)
    img = np.clip(img, 0, 255).astype(np.uint8)
    sigma = rng.uniform(*BLUR_SIGMA)
    if sigma > 0.3:
        img = cv2.GaussianBlur(img, (0, 0), sigma)
    return img, sid, answers, kinds


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="สร้างภาพทดสอบสังเคราะห์")
    parser.add_argument("--n", type=int, default=100)
    parser.add_argument("--out", default=str(C.SAMPLES_DIR / "synthetic"))
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--questions", type=int, default=C.NUM_QUESTIONS)
    parser.add_argument("--sheet", default=str(C.SAMPLES_DIR / "answer_sheet.png"))
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    rng = np.random.default_rng(args.seed)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    sheet_path = Path(args.sheet)
    base = cv2.imread(str(sheet_path)) if sheet_path.is_file() and args.questions == C.NUM_QUESTIONS else None
    if base is None:
        base = generate_png_image(args.questions)

    # เฉลยสุ่มแยก
    key = {q: str(rng.choice(list(C.CHOICES))) for q in range(1, args.questions + 1)}
    with (out / "answer_key.csv").open("w", newline="", encoding="utf-8") as f:
        wr = csv.writer(f)
        wr.writerow(["question", "answer"])
        wr.writerows(sorted(key.items()))

    qcols = [f"q{i}" for i in range(1, args.questions + 1)]
    with (out / "ground_truth.csv").open("w", newline="", encoding="utf-8") as gt, \
            (out / "ground_truth_kinds.csv").open("w", newline="", encoding="utf-8") as kt:
        gw, kw = csv.writer(gt), csv.writer(kt)
        gw.writerow(["filename", "student_id", *qcols])
        kw.writerow(["filename", *qcols])
        for i in range(1, args.n + 1):
            img, sid, answers, kinds = synth_one(rng, base, args.questions)
            name = f"sheet_{i:04d}.jpg"
            quality = int(rng.integers(JPEG_QUALITY[0], JPEG_QUALITY[1] + 1))
            cv2.imwrite(str(out / name), img, [cv2.IMWRITE_JPEG_QUALITY, quality])
            gw.writerow([name, sid, *[answers[q] for q in range(1, args.questions + 1)]])
            kw.writerow([name, *[kinds[q] for q in range(1, args.questions + 1)]])
            if i % 10 == 0 or i == args.n:
                log.info("สร้างแล้ว %d/%d", i, args.n)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
