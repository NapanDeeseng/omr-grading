"""ค่าคงที่ทั้งหมดของระบบ OMR: layout กระดาษ (หน่วย mm), ค่าเกณฑ์ และพารามิเตอร์ประมวลผลภาพ

ทุกตัวเลขที่ใช้ในแพ็กเกจ omr ต้องมาจากไฟล์นี้ เพื่อให้จูนได้จากที่เดียว
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

# ---------------------------------------------------------------------------
# path ของโปรเจกต์
# ---------------------------------------------------------------------------
PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent
SAMPLES_DIR: Path = PROJECT_ROOT / "samples"
DEBUG_DIR: Path = PROJECT_ROOT / "debug"
REPORTS_DIR: Path = PROJECT_ROOT / "reports"

# ---------------------------------------------------------------------------
# ข้อสอบ
# ---------------------------------------------------------------------------
NUM_QUESTIONS: int = 40              # รองรับ 1–60 (แก้ค่านี้อย่างเดียว)
MAX_QUESTIONS: int = 60
CHOICES: tuple[str, ...] = ("A", "B", "C", "D")
QUESTIONS_PER_COLUMN: int = 20
STUDENT_ID_DIGITS: int = 5
DIGITS: tuple[int, ...] = tuple(range(10))

# ---------------------------------------------------------------------------
# กระดาษ (mm)
# ---------------------------------------------------------------------------
PAGE_WIDTH_MM: float = 210.0
PAGE_HEIGHT_MM: float = 297.0

# ภาพหลัง warp (px) ≈ 150 DPI
WARP_WIDTH_PX: int = 1240
WARP_HEIGHT_PX: int = 1754
PDF_POINTS_PER_MM: float = 72.0 / 25.4

# มาร์กเกอร์มุม
MARKER_SIZE_MM: float = 12.0
MARKER_MARGIN_MM: float = 10.0       # ระยะจากขอบกระดาษถึงขอบมาร์กเกอร์
MARKER_HOLE_MM: float = 4.0          # ช่องขาวกลางมาร์กเกอร์ TL
MARKER_CLEARANCE_MM: float = 5.0     # ขอบว่างรอบมาร์กเกอร์ขั้นต่ำ

# bubble
BUBBLE_DIAMETER_MM: float = 5.0
BUBBLE_PITCH_X_MM: float = 8.0
BUBBLE_PITCH_Y_MM: float = 9.0
BUBBLE_LINE_WIDTH_MM: float = 0.25
BUBBLE_LABEL_GRAY: int = 185         # สีตัวอักษรในวง (0=ดำ 255=ขาว)
BUBBLE_LABEL_FONT_PT: float = 7.0

# ส่วนหัว
TITLE_Y_MM: float = 16.5
SUBTITLE_Y_MM: float = 23.0
TITLE_FONT_PT: float = 16.0
SUBTITLE_FONT_PT: float = 9.0
BODY_FONT_PT: float = 9.0
SMALL_FONT_PT: float = 7.5
THAI_FONT_SCALE: float = 1.35        # ขยายฟอนต์ไทย (TH Sarabun ตัวเล็กกว่าละตินที่ pt เท่ากัน)
INFO_LEFT_MM: float = 30.0
INFO_LINE_END_MM: float = 132.0
INFO_FIRST_Y_MM: float = 36.0
INFO_LINE_PITCH_MM: float = 9.0
INSTRUCTION_TOP_MM: float = 72.0
INSTRUCTION_LINE_PITCH_MM: float = 5.0
EXAMPLE_BUBBLE_DIAMETER_MM: float = 4.0
EXAMPLE_ROW_OFFSET_MM: float = 0.5
EXAMPLE_OK_X_MM: float = 17.0
EXAMPLE_WRONG_LABEL_X_MM: float = 30.0
EXAMPLE_WRONG_X_MM: float = 50.0
INFO_LABEL_WIDTH_MM: float = 18.0
INFO_UNDERLINE_OFFSET_MM: float = 2.0
QUESTION_NUMBER_GAP_MM: float = 1.5

# บล็อกรหัสนักศึกษา (มุมขวาบน)
ID_FIRST_CENTER_X_MM: float = 150.0
ID_PITCH_X_MM: float = 8.0
ID_PITCH_Y_MM: float = 6.0           # 10 แถวต้องอยู่ในส่วนหัว จึงใช้ระยะแนวตั้งแคบกว่า
ID_LABEL_Y_MM: float = 30.0
ID_WRITE_BOX_TOP_MM: float = 32.0
ID_WRITE_BOX_HEIGHT_MM: float = 7.0
ID_WRITE_BOX_WIDTH_MM: float = 6.5
ID_FIRST_CENTER_Y_MM: float = 43.5
ID_FRAME_PAD_MM: float = 4.0

# บล็อกคำตอบ
ANSWER_SEPARATOR_Y_MM: float = 103.5
ANSWER_FIRST_CENTER_Y_MM: float = 108.0
ANSWER_REGION_LEFT_MM: float = 30.0
ANSWER_REGION_RIGHT_MM: float = 180.0  # เว้นระยะจากมาร์กเกอร์ขวาล่างเมื่อมี 3 คอลัมน์ (60 ข้อ)
ANSWER_COL_PITCH_MAX_MM: float = 70.0
ANSWER_NUMBER_WIDTH_MM: float = 9.0  # ช่องเลขข้อทางซ้ายของ bubble A
FOOTER_Y_MM: float = 292.0

# ---------------------------------------------------------------------------
# ค่าเกณฑ์การอ่าน (จูนด้วย tools/evaluate.py)
# ---------------------------------------------------------------------------
FILL_THRESHOLD: float = 0.45         # สัดส่วนพิกเซลดำขั้นต่ำที่นับว่าฝน
FAINT_THRESHOLD: float = 0.25        # ต่ำกว่านี้ = ว่าง, ระหว่างนี้กับ FILL = ฝนจาง
CONFIDENCE_THRESHOLD: float = 0.60
BUBBLE_SAMPLE_RATIO: float = 0.75    # ใช้วงในของ bubble เพื่อตัดเส้นขอบ
CONFIDENCE_SCALE: float = 0.40       # ส่วนต่าง r1-r2 ที่ถือว่ามั่นใจเต็ม 100%
DEBUG: bool = False

# ---------------------------------------------------------------------------
# preprocess: หามาร์กเกอร์
# ---------------------------------------------------------------------------
DETECT_LONG_SIDE_PX: int = 1600
DETECT_BLUR_KSIZE: int = 5
DETECT_ADAPTIVE_BLOCK: int = 51
DETECT_ADAPTIVE_C: int = 10
DETECT_CLOSE_KSIZE: int = 3
DETECT_APPROX_EPS: float = 0.04      # สัดส่วนของเส้นรอบรูปสำหรับ approxPolyDP
# ด้านของมาร์กเกอร์เทียบกับด้านยาวภาพที่ย่อแล้ว (กระดาษกินพื้นที่ ~25%–100% ของภาพ)
MARKER_MIN_SIDE_FRAC: float = 0.008
MARKER_MAX_SIDE_FRAC: float = 0.07
MARKER_ASPECT_MIN: float = 0.75
MARKER_ASPECT_MAX: float = 1.33
MARKER_MIN_SOLIDITY: float = 0.85
MARKER_MIN_EXTENT: float = 0.80      # พื้นที่/พื้นที่ minAreaRect (วงกลมทึบ ≈ 0.785)
MARKER_MAX_INSIDE_TO_RING: float = 0.65  # ความสว่างในรูปทรง/วงรอบนอก (กันกรอบกลวง)
MARKER_MAX_CANDIDATES: int = 24
MARKER_MAX_AREA_RATIO: float = 2.5   # มาร์กเกอร์ที่ใหญ่สุด/เล็กสุดใน 4 ตัว
# ขนาดมาร์กเกอร์เทียบกับระยะระหว่างจุดกึ่งกลาง (ตามแบบ 12/178 และ 12/265)
MARKER_TO_SPAN_MIN: float = 0.025
MARKER_TO_SPAN_MAX: float = 0.12
# อัตราส่วนกว้าง/สูงของกรอบ 4 มาร์กเกอร์ (ตามแบบ 178/265 ≈ 0.67)
QUAD_ASPECT_MIN: float = 0.45
QUAD_ASPECT_MAX: float = 0.95

# ตรวจทิศ: เปรียบเทียบความสว่างกลางมาร์กเกอร์ TL กับ BR
ORIENT_SAMPLE_FRAC: float = 0.5      # ใช้ขนาดครึ่งหนึ่งของช่องขาว
ORIENT_MIN_DIFF: float = 40.0        # ต่างกันขั้นต่ำ (ระดับเทา) ถึงจะเชื่อ

# binarize
BG_KERNEL_PX: int = 61               # kernel ประมาณพื้นหลัง (> bubble ~30px + ฝนเลยขอบ)
BIN_ADAPTIVE_BLOCK: int = 51
BIN_ADAPTIVE_C: int = 25              # จูนแล้ว: 30 ทำฝนจางหาย, 20 ทำรอยลบเกิน FAINT (ดู DECISIONS.md)
NORMALIZE_MAX: float = 255.0
# SciPy: ลด noise ก่อน threshold และลบจุดหมึกโดด ๆ หลัง threshold
DENOISE_SIGMA: float = 1.0           # gaussian_filter บนภาพที่ normalize แล้ว (0 = ปิด)
SPECKLE_OPEN_PX: int = 2             # binary_opening ขนาด n×n (0 = ปิด)

# ---------------------------------------------------------------------------
# preprocess: หาขอบกระดาษ (สำรองเมื่อหามาร์กเกอร์ไม่ครบ)
# ---------------------------------------------------------------------------
PAPER_CANNY_LOW: int = 50
PAPER_CANNY_HIGH: int = 150
PAPER_DILATE_PX: int = 5
PAPER_MIN_AREA_FRAC: float = 0.20    # กระดาษต้องกินพื้นที่ ≥ 20% ของภาพ
PAPER_MAX_AREA_FRAC: float = 0.95    # ใหญ่กว่านี้คือขอบภาพ (ต้องเห็นพื้นหลังรอบกระดาษ)
PAPER_ASPECT_MIN: float = 0.60       # กว้าง/สูง ของ A4 = 0.707
PAPER_ASPECT_MAX: float = 0.82

# ---------------------------------------------------------------------------
# ตรวจคุณภาพภาพ (OpenCV + scikit-image regionprops)
# ---------------------------------------------------------------------------
# เตือนเท่านั้น (ไม่กระทบคะแนน) — ค่าตั้งต่ำกว่าช่วงของภาพสังเคราะห์ที่ยังอ่านถูก 100% (ดู DECISIONS.md)
QUALITY_BLUR_MIN_VAR: float = 8.0    # Laplacian variance ต่ำกว่านี้ = ภาพเบลอ
QUALITY_PAPER_PERCENTILE: float = 90.0
QUALITY_DARK_PAPER: float = 90.0     # ความสว่างกระดาษ (percentile 90) ต่ำกว่านี้ = มืดเกิน
# แสงสะท้อน = บริเวณอิ่มตัว (≥ LEVEL) ที่สว่างกว่ากระดาษส่วนใหญ่ (median) อย่างน้อย MARGIN
QUALITY_GLARE_LEVEL: int = 250
QUALITY_GLARE_MARGIN: int = 30
QUALITY_GLARE_MIN_AREA_PX: int = 1500  # บริเวณเล็กกว่านี้ไม่นับ (ภาพหลัง warp)

# ---------------------------------------------------------------------------
# YOLOv8n: ตรวจจับกรอบบริเวณที่มีปัญหาบนกระดาษ (ไม่บังคับ — ใช้เมื่อมีไฟล์โมเดล)
# ---------------------------------------------------------------------------
MODELS_DIR: Path = PROJECT_ROOT / "models"
YOLO_WEIGHTS: Path = MODELS_DIR / "omr_problems_yolov8n.pt"
YOLO_CLASSES: tuple[str, ...] = ("multi_mark", "faint_mark", "erasure")
YOLO_CLASS_TH: dict[str, str] = {"multi_mark": "ฝนหลายตัวเลือก", "faint_mark": "ฝนจาง", "erasure": "รอยลบ"}
YOLO_IMGSZ: int = 640
YOLO_CONF: float = 0.35
YOLO_ROW_MIN_OVERLAP: float = 0.30   # สัดส่วนกรอบที่ต้องทับแถวคำตอบถึงจะผูกกับข้อนั้น
YOLO_ENABLED: bool = True

# ---------------------------------------------------------------------------
# annotate (BGR)
# ---------------------------------------------------------------------------
COLOR_CORRECT: tuple[int, int, int] = (40, 170, 40)
COLOR_WRONG: tuple[int, int, int] = (40, 40, 220)
COLOR_UNCERTAIN: tuple[int, int, int] = (0, 200, 240)
COLOR_ROW_ALERT: tuple[int, int, int] = (0, 140, 255)
COLOR_TEXT: tuple[int, int, int] = (150, 40, 20)
COLOR_AI_BOX: tuple[int, int, int] = (200, 40, 200)
COLOR_GLARE: tuple[int, int, int] = (255, 160, 0)
ANNOTATE_THICK: int = 3
ANNOTATE_THIN: int = 1
ANNOTATE_RING_EXTRA_PX: int = 4
ANNOTATE_DASH_SEGMENTS: int = 12
ANNOTATE_ROW_PAD_PX: int = 6
ANNOTATE_FONT_SCALE: float = 1.6
ANNOTATE_FONT_THICK: int = 4
ANNOTATE_SCORE_POS_PX: tuple[int, int] = (160, 125)

# ---------------------------------------------------------------------------
# pipeline
# ---------------------------------------------------------------------------
SUPPORTED_EXTENSIONS: tuple[str, ...] = (".jpg", ".jpeg", ".png")
UNSUPPORTED_HINT_EXTENSIONS: tuple[str, ...] = (".heic", ".heif")
PREVIEW_MAX_SIDE_PX: int = 1200      # ขนาดภาพต้นฉบับที่เก็บไว้แสดงผล

# โฟลเดอร์เก็บผล (ไม่ใช้ฐานข้อมูล — เก็บเป็นไฟล์ JSON/Excel/ภาพ)
RESULTS_DIR: Path = PROJECT_ROOT / "results"
SESSIONS_DIR: Path = RESULTS_DIR / "sessions"

# โหมดสาธารณะ: เปิดด้วย OMR_PUBLIC=1 เมื่อ deploy เป็นเว็บที่ใครก็เข้าได้
# ระบบจะไม่เขียนภาพ/รหัสนักเรียนลงเซิร์ฟเวอร์เลย ผู้ใช้ต้องดาวน์โหลด Excel เก็บเอง
# (ไฟล์บนเซิร์ฟเวอร์ฟรีหายเมื่อ restart อยู่แล้ว และเป็นข้อมูลส่วนบุคคลของนักเรียนคนอื่น)
PUBLIC_MODE: bool = os.getenv("OMR_PUBLIC", "").strip().lower() in ("1", "true", "yes")

# ภาพตัวอย่างให้คนที่ยังไม่มีกระดาษคำตอบกดลองได้ทันที
DEMO_IMAGE: Path = SAMPLES_DIR / "demo_sheet.jpg"
DEMO_KEY: Path = SAMPLES_DIR / "demo_answer_key.csv"


@dataclass(frozen=True)
class Thresholds:
    """ชุดค่าเกณฑ์ที่ปรับได้จาก dashboard"""

    fill: float = FILL_THRESHOLD
    faint: float = FAINT_THRESHOLD
    confidence: float = CONFIDENCE_THRESHOLD
    sample_ratio: float = BUBBLE_SAMPLE_RATIO
