"""รวมทุกขั้นตอน: โหลดภาพ → หามาร์กเกอร์ → warp → ตรวจทิศ → threshold → อ่าน → ให้คะแนน → annotate"""

from __future__ import annotations

import importlib.util
import logging
import struct
import time
from dataclasses import replace
from pathlib import Path

import cv2
import numpy as np

from omr import config as C
from omr import detector, preprocess, quality, reader
from omr.annotate import annotate
from omr.errors import ImageLoadError, MarkerNotFoundError, OMRError, PaperNotFoundError
from omr.grader import AnswerKey, grade, manual_read
from omr.models import STATUS_FAINT, STATUS_MULTI, STATUS_OK, ReadResult, SheetResult

log = logging.getLogger(__name__)

EXIF_ORIENTATION_TAG = 0x0112
JPEG_SOI = b"\xff\xd8"
JPEG_APP1 = 0xE1
EXIF_HEADER = b"Exif\x00\x00"


def read_exif_orientation(data: bytes) -> int:
    """อ่านค่า EXIF orientation (1–8) จาก JPEG bytes คืน 1 ถ้าไม่มี"""
    if not data.startswith(JPEG_SOI):
        return 1
    pos = 2
    try:
        while pos + 4 <= len(data):
            if data[pos] != 0xFF:
                return 1
            marker = data[pos + 1]
            seg_len = struct.unpack(">H", data[pos + 2: pos + 4])[0]
            if marker == JPEG_APP1 and data[pos + 4: pos + 10] == EXIF_HEADER:
                tiff = data[pos + 10: pos + 2 + seg_len]
                endian = "<" if tiff[:2] == b"II" else ">"
                ifd = struct.unpack(endian + "I", tiff[4:8])[0]
                count = struct.unpack(endian + "H", tiff[ifd: ifd + 2])[0]
                for i in range(count):
                    entry = tiff[ifd + 2 + i * 12: ifd + 14 + i * 12]
                    tag = struct.unpack(endian + "H", entry[:2])[0]
                    if tag == EXIF_ORIENTATION_TAG:
                        return int(struct.unpack(endian + "H", entry[8:10])[0])
                return 1
            if marker in (0xDA, 0xD9):  # เริ่มข้อมูลภาพแล้ว ไม่มี EXIF
                return 1
            pos += 2 + seg_len
    except (struct.error, IndexError):
        return 1
    return 1


def apply_exif_orientation(image: np.ndarray, orientation: int) -> np.ndarray:
    """หมุน/กลับภาพตามค่า EXIF orientation"""
    ops: dict[int, list[int | str]] = {
        2: ["flipx"], 3: [cv2.ROTATE_180], 4: ["flipy"], 5: ["flipx", cv2.ROTATE_90_COUNTERCLOCKWISE],
        6: [cv2.ROTATE_90_CLOCKWISE], 7: ["flipx", cv2.ROTATE_90_CLOCKWISE], 8: [cv2.ROTATE_90_COUNTERCLOCKWISE],
    }
    for op in ops.get(orientation, []):
        if op == "flipx":
            image = cv2.flip(image, 1)
        elif op == "flipy":
            image = cv2.flip(image, 0)
        else:
            image = cv2.rotate(image, op)
    return image


def heic_supported() -> bool:
    """เครื่องนี้เปิดไฟล์ HEIC/HEIF จาก iPhone ได้หรือไม่ (ต้องมี pillow-heif)"""
    return importlib.util.find_spec("pillow_heif") is not None


def _decode_heic(data: bytes) -> np.ndarray:
    """แปลง HEIC/HEIF เป็นภาพ BGR — pillow-heif หมุนภาพตาม EXIF ให้แล้ว"""
    import pillow_heif

    try:
        img = pillow_heif.open_heif(data, convert_hdr_to_8bit=True)
        rgb = np.asarray(img.to_pillow().convert("RGB"))
    except Exception as exc:  # noqa: BLE001 — ไฟล์เสียต้องขึ้นข้อความเดียวกับภาพชนิดอื่น
        raise ImageLoadError(f"เปิดไฟล์ HEIC ไม่ได้: {exc}") from exc
    return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)


def load_image(source: bytes | str | Path, filename: str = "") -> np.ndarray:
    """โหลดภาพจาก bytes หรือ path พร้อมแก้ EXIF orientation"""
    name = filename or (Path(source).name if isinstance(source, (str, Path)) else "")
    ext = Path(name).suffix.lower()
    heic = ext in C.UNSUPPORTED_HINT_EXTENSIONS
    if heic and not heic_supported():
        raise ImageLoadError("ไม่รองรับไฟล์ HEIC/HEIF ในเครื่องนี้ ติดตั้งด้วย pip install pillow-heif "
                             "หรือแปลงเป็น JPG ก่อน (iPhone: ตั้งค่ากล้องเป็น 'เข้ากันได้มากที่สุด')")
    if ext and not heic and ext not in C.SUPPORTED_EXTENSIONS:
        raise ImageLoadError(f"ไม่รองรับไฟล์ชนิด {ext} (รองรับ {', '.join(C.SUPPORTED_EXTENSIONS)})")
    if isinstance(source, (str, Path)):
        try:
            data = Path(source).read_bytes()
        except OSError as exc:
            raise ImageLoadError(f"เปิดไฟล์ไม่ได้: {exc}") from exc
    else:
        data = bytes(source)
    if not data:
        raise ImageLoadError("ไฟล์ภาพว่างเปล่า")
    if heic:
        return _decode_heic(data)
    image = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR | cv2.IMREAD_IGNORE_ORIENTATION)
    if image is None:
        raise ImageLoadError("ไฟล์ภาพเสียหรือไม่ใช่ภาพที่รองรับ")
    return apply_exif_orientation(image, read_exif_orientation(data))


def _preview(image: np.ndarray) -> np.ndarray:
    h, w = image.shape[:2]
    s = min(1.0, C.PREVIEW_MAX_SIDE_PX / max(h, w))
    return cv2.resize(image, (int(w * s), int(h * s)), interpolation=cv2.INTER_AREA) if s < 1 else image


def align_sheet(image: np.ndarray, debug_dir: Path | None = None) -> tuple[np.ndarray, bool]:
    """ปรับระนาบกระดาษด้วยมาร์กเกอร์ 4 มุม ถ้าไม่ครบลองใช้ขอบกระดาษ คืน (ภาพ 1240×1754, ใช้ขอบกระดาษหรือไม่)"""
    try:
        return preprocess.warp(image, preprocess.find_markers(image, debug_dir)), False
    except MarkerNotFoundError as marker_error:
        try:
            corners = preprocess.find_paper(image, debug_dir)
        except PaperNotFoundError:
            raise marker_error from None
    log.info("หามาร์กเกอร์ไม่ครบ ใช้ขอบกระดาษแทน")
    return preprocess.warp_paper(image, corners), True


def grade_image(
    source: bytes | str | Path,
    answer_key: AnswerKey,
    filename: str = "",
    thresholds: C.Thresholds | None = None,
    debug: bool = C.DEBUG,
    keep_images: bool = True,
    detect_problems: bool = C.YOLO_ENABLED,
) -> SheetResult:
    """ตรวจกระดาษคำตอบหนึ่งแผ่น ไม่ raise — ถ้าผิดพลาดจะคืน SheetResult ที่มี error"""
    start = time.perf_counter()
    th = thresholds or C.Thresholds()
    filename = filename or (Path(source).name if isinstance(source, (str, Path)) else "image")
    result = SheetResult(filename=filename)
    debug_dir = C.DEBUG_DIR / Path(filename).stem if debug else None
    try:
        image = load_image(source, filename)
        if keep_images:
            result.original_preview = _preview(image)
        warped, result.used_paper_fallback = align_sheet(image, debug_dir)
        warped, rotated = preprocess.fix_orientation(warped)
        preprocess.save_debug(debug_dir, "04_warped.png", warped)
        binary = preprocess.binarize(warped, debug_dir)

        result.rotated = rotated
        result.warnings, glare = quality.assess(warped)
        if result.used_paper_fallback:
            result.warnings.insert(0, "หามาร์กเกอร์ไม่ครบ จึงใช้ขอบกระดาษแทน — ตำแหน่งอาจคลาดเล็กน้อย ควรตรวจทาน")
        result.problem_boxes = detector.assign_questions(glare) + (
            detector.detect(warped) if detect_problems else [])
        result.student_id, result.id_valid, result.id_confidence, result.id_reads = reader.read_student_id(binary, th)
        result.answer_reads = reader.read_answers(binary, C.NUM_QUESTIONS, th)
        grade(result.answer_reads, answer_key, result)
        result.annotated_image = annotate(warped, result)
        if keep_images:
            result.warped_image = warped
        else:
            result.original_preview = None
    except OMRError as exc:
        log.warning("%s: %s", filename, exc)
        result.error = str(exc)
    except Exception as exc:  # noqa: BLE001 — ห้าม crash ไม่ว่ากรณีใด
        log.exception("ประมวลผล %s ล้มเหลว", filename)
        result.error = f"เกิดข้อผิดพลาดระหว่างประมวลผลภาพ: {exc}"
    result.processing_ms = round((time.perf_counter() - start) * 1000.0, 1)
    return result


def read_key_image(
    source: bytes | str | Path,
    filename: str = "",
    thresholds: C.Thresholds | None = None,
) -> tuple[AnswerKey, list[int]]:
    """อ่านเฉลยจากภาพกระดาษคำตอบที่ครูฝนเฉลยไว้ คืน (เฉลย, ข้อที่ควรตรวจทาน) — raise OMRError ถ้าอ่านภาพไม่ได้

    ข้อว่าง = ไม่ใช้ข้อนั้น, ข้อที่ฝนหลายช่องไม่ใส่ในเฉลย, ข้อที่ฝนจาง/ไม่มั่นใจใส่ไว้แต่ให้ครูตรวจทาน
    """
    th = thresholds or C.Thresholds()
    warped, _ = align_sheet(load_image(source, filename))
    warped, _ = preprocess.fix_orientation(warped)
    reads = reader.read_answers(preprocess.binarize(warped), C.NUM_QUESTIONS, th)
    key = {q: r.answer for q, r in reads.items() if r.status in (STATUS_OK, STATUS_FAINT)}
    review = sorted(q for q, r in reads.items() if r.status == STATUS_MULTI or (q in key and r.uncertain))
    if not key:
        raise OMRError("ไม่พบข้อที่ฝนไว้ในภาพ — ฝนเฉลยลงกระดาษคำตอบให้เข้มเต็มวง แล้วถ่ายให้เห็นสี่เหลี่ยมดำครบ 4 มุม")
    return key, review


def regrade(result: SheetResult, answer_key: AnswerKey, thresholds: C.Thresholds | None = None) -> SheetResult:
    """ตรวจใหม่จากค่า ratio ที่เก็บไว้ (ใช้เมื่อเปลี่ยนเฉลยหรือค่าเกณฑ์) โดยคงคำตอบที่ผู้ตรวจแก้ไว้"""
    if result.error is not None:
        return result
    th = thresholds or C.Thresholds()
    edited = {q.number for q in result.questions if q.edited}
    reads: dict[int, ReadResult] = {}
    for q, rr in result.answer_reads.items():
        reads[q] = rr if (q in edited or not rr.ratios) else reader.read_group(rr.ratios, th)
    result.answer_reads = reads
    if not result.reviewed:
        result.id_reads = [r if not r.ratios else reader.read_group(r.ratios, th) for r in result.id_reads]
        result.student_id, result.id_valid, result.id_confidence = reader.combine_student_id(result.id_reads)
    grade(reads, answer_key, result)
    if result.warped_image is not None:
        result.annotated_image = annotate(result.warped_image, result)
    return result


def apply_review(
    result: SheetResult,
    answer_key: AnswerKey,
    edits: dict[int, str],
    student_id: str | None = None,
) -> SheetResult:
    """บันทึกการแก้ไขของผู้ตรวจ แล้วคำนวณคะแนนและภาพใหม่"""
    if result.error is not None:
        return result
    for q, ans in edits.items():
        result.answer_reads[q] = manual_read(ans)
    for q in result.questions:  # ทำเครื่องหมายก่อน grade เพื่อไม่ให้ flag จาก YOLO กลับมา
        if q.number in edits:
            q.edited = True
    if student_id is not None and student_id != result.student_id:
        digits = student_id.strip()
        result.id_reads = [
            replace(manual_read(""), answer=d, status=STATUS_OK) if d.isdigit() else manual_read("") for d in digits
        ]
        result.student_id, result.id_valid = digits, digits.isdigit() and len(digits) == C.STUDENT_ID_DIGITS
        result.id_confidence = 1.0
    grade(result.answer_reads, answer_key, result)
    result.reviewed = True
    if result.warped_image is not None:
        result.annotated_image = annotate(result.warped_image, result)
    return result
