"""บันทึก/เปิดผลการตรวจเป็นไฟล์ (ไม่ใช้ฐานข้อมูล)

แต่ละรอบการตรวจเก็บเป็นโฟลเดอร์ใน results/sessions/<ชื่อ>/
    session.json        ข้อมูลผลตรวจทั้งหมด + เฉลย (อ่านด้วยโปรแกรมอื่นได้)
    results.xlsx        ไฟล์ Excel ณ เวลาที่บันทึก
    images/<n>_warped.jpg, images/<n>_original.jpg   ภาพสำหรับแสดงผล/แก้ไขภายหลัง
"""

from __future__ import annotations

import json
import re
import shutil
from dataclasses import asdict, fields
from datetime import datetime
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from omr import __version__
from omr import config as C
from omr.annotate import annotate
from omr.exporter import export_excel
from omr.grader import AnswerKey
from omr.models import ProblemBox, QuestionResult, ReadResult, SheetResult

FORMAT_VERSION = 1
SESSION_FILE = "session.json"
EXCEL_FILE = "results.xlsx"
IMAGES_DIR = "images"
JPEG_QUALITY = 92
_IMAGE_FIELDS = {"annotated_image", "warped_image", "original_preview"}


def _safe_name(name: str) -> str:
    """ชื่อโฟลเดอร์ที่ปลอดภัย (คงภาษาไทยไว้ ตัดอักขระต้องห้ามของ Windows)"""
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name).strip(" .")
    return name or datetime.now().strftime("%Y%m%d_%H%M%S")


def _sheet_to_dict(r: SheetResult) -> dict[str, Any]:
    data = {f.name: getattr(r, f.name) for f in fields(r) if f.name not in _IMAGE_FIELDS}
    data["questions"] = [asdict(q) for q in r.questions]
    data["id_reads"] = [asdict(x) for x in r.id_reads]
    data["answer_reads"] = {str(q): asdict(x) for q, x in r.answer_reads.items()}
    data["problem_boxes"] = [asdict(b) for b in r.problem_boxes]
    return data


def _sheet_from_dict(d: dict[str, Any]) -> SheetResult:
    known = {f.name for f in fields(SheetResult)} - _IMAGE_FIELDS
    r = SheetResult(**{k: v for k, v in d.items() if k in known})
    r.questions = [QuestionResult(**q) for q in d.get("questions", [])]
    r.id_reads = [ReadResult(**x) for x in d.get("id_reads", [])]
    r.answer_reads = {int(q): ReadResult(**x) for q, x in d.get("answer_reads", {}).items()}
    r.problem_boxes = [ProblemBox(**{**b, "box": tuple(b["box"])}) for b in d.get("problem_boxes", [])]
    return r


def _write_jpg(path: Path, img: np.ndarray | None) -> str | None:
    if img is None:
        return None
    ok, enc = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
    if not ok:
        return None
    path.write_bytes(enc.tobytes())
    return path.name


def _read_jpg(path: Path) -> np.ndarray | None:
    if not path.is_file():
        return None
    return cv2.imdecode(np.frombuffer(path.read_bytes(), np.uint8), cv2.IMREAD_COLOR)


def save_session(results: list[SheetResult], answer_key: AnswerKey, name: str = "",
                 root: Path = C.SESSIONS_DIR) -> Path:
    """บันทึกผลการตรวจทั้งหมดลงโฟลเดอร์ (เขียนทับถ้าชื่อซ้ำ) คืน path ของโฟลเดอร์"""
    folder = root / _safe_name(name)
    if folder.exists():
        shutil.rmtree(folder)
    (folder / IMAGES_DIR).mkdir(parents=True)
    sheets = []
    for i, r in enumerate(results):
        d = _sheet_to_dict(r)
        d["images"] = {
            "warped": _write_jpg(folder / IMAGES_DIR / f"{i:04d}_warped.jpg", r.warped_image),
            "original": _write_jpg(folder / IMAGES_DIR / f"{i:04d}_original.jpg", r.original_preview),
        }
        sheets.append(d)
    payload = {
        "format_version": FORMAT_VERSION,
        "app_version": __version__,
        "saved_at": datetime.now().isoformat(timespec="seconds"),
        "num_questions": C.NUM_QUESTIONS,
        "answer_key": {str(q): a for q, a in sorted(answer_key.items())},
        "sheets": sheets,
    }
    (folder / SESSION_FILE).write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    (folder / EXCEL_FILE).write_bytes(export_excel(results, answer_key))
    return folder


def load_session(folder: Path) -> tuple[list[SheetResult], AnswerKey]:
    """เปิดผลการตรวจที่บันทึกไว้ คืน (ผลตรวจ, เฉลย) — ภาพ annotate สร้างใหม่จากภาพหลัง warp"""
    payload = json.loads((folder / SESSION_FILE).read_text(encoding="utf-8"))
    key = {int(q): a for q, a in payload.get("answer_key", {}).items()}
    results = []
    for d in payload.get("sheets", []):
        images = d.pop("images", {}) or {}
        r = _sheet_from_dict(d)
        if images.get("warped"):
            r.warped_image = _read_jpg(folder / IMAGES_DIR / images["warped"])
        if images.get("original"):
            r.original_preview = _read_jpg(folder / IMAGES_DIR / images["original"])
        if r.warped_image is not None and r.error is None:
            r.annotated_image = annotate(r.warped_image, r)
        results.append(r)
    return results, key


def list_sessions(root: Path = C.SESSIONS_DIR) -> list[dict[str, Any]]:
    """รายการรอบการตรวจที่บันทึกไว้ เรียงใหม่สุดก่อน"""
    if not root.is_dir():
        return []
    out = []
    for folder in root.iterdir():
        f = folder / SESSION_FILE
        if not f.is_file():
            continue
        try:
            payload = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        out.append({"name": folder.name, "path": folder, "saved_at": payload.get("saved_at", ""),
                    "sheets": len(payload.get("sheets", []))})
    return sorted(out, key=lambda s: s["saved_at"], reverse=True)


def delete_session(folder: Path, root: Path = C.SESSIONS_DIR) -> None:
    """ลบโฟลเดอร์ผลการตรวจ (เฉพาะที่อยู่ใน root เท่านั้น)"""
    if folder.resolve().parent != root.resolve():
        raise ValueError("ลบได้เฉพาะโฟลเดอร์ใน results/sessions")
    shutil.rmtree(folder)
