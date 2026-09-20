# คู่มือสำหรับนักพัฒนา (Developer Guide)

คู่มือนี้บอกคำสั่ง terminal ทั้งหมดที่ใช้ตั้งแต่ติดตั้งจนถึงพัฒนาต่อ ส่วนภาพรวมอัลกอริทึมอยู่ใน `README.md`
และเหตุผลของการตัดสินใจแต่ละข้ออยู่ใน `DECISIONS.md`

ตัวอย่างคำสั่งเขียนสำหรับ **Windows PowerShell** ส่วน macOS/Linux ต่างกันแค่คำสั่ง activate (ระบุไว้ในแต่ละขั้น)

---

## 1. สิ่งที่ต้องมีก่อน

- Python **3.11–3.13** (ทดสอบบน 3.13.5) — ตรวจด้วย `python --version`
- พื้นที่ว่างประมาณ 2 GB (PyTorch ที่ติดมากับ ultralytics ใหญ่ที่สุด)
- อินเทอร์เน็ตตอนติดตั้งครั้งแรก (หลังจากนั้นรันแบบออฟไลน์ได้ ยกเว้นฟอนต์ Sarabun บนหน้าเว็บ)
- ไม่ต้องติดตั้งฐานข้อมูลใด ๆ — ระบบเก็บผลเป็นไฟล์ใน `results/sessions/`

## 2. ติดตั้งครั้งแรก

```powershell
cd omr-grading

# สร้าง virtual environment (ถ้ามีโฟลเดอร์ .venv เดิมที่ใช้ไม่ได้ ให้ลบทิ้งก่อน: Remove-Item -Recurse -Force .venv)
python -m venv .venv

# เปิดใช้งาน venv
.venv\Scripts\Activate.ps1          # PowerShell
# .venv\Scripts\activate.bat        # Command Prompt
# source .venv/bin/activate         # macOS / Linux

# ติดตั้งไลบรารีทั้งหมด (Streamlit, ultralytics/YOLOv8n, OpenCV, imutils, scikit-image, SciPy, NumPy, Pandas, OpenPyXL)
python -m pip install --upgrade pip
pip install -r requirements.txt
```

ถ้า PowerShell ขึ้นว่า "running scripts is disabled" ให้รันครั้งเดียว:
`Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`

ตรวจว่าติดตั้งครบ:

```powershell
python -c "import cv2, imutils, skimage, scipy, ultralytics, streamlit, pandas, openpyxl; print('OK')"
python -m pytest -q
```

## 3. รันระบบ

```powershell
streamlit run app.py
```

เปิดเบราว์เซอร์ที่ http://localhost:8501 (หยุดด้วย `Ctrl + C`)

| ต้องการ | คำสั่ง |
|---|---|
| เปลี่ยนพอร์ต | `streamlit run app.py --server.port 8600` |
| ให้เครื่องอื่นในวง LAN เข้าได้ | `streamlit run app.py --server.address 0.0.0.0` |
| ไม่เปิดเบราว์เซอร์อัตโนมัติ | `streamlit run app.py --server.headless true` |

แก้ไฟล์ `app.py` แล้วกด "Rerun" มุมขวาบนของหน้าเว็บได้เลย แต่ถ้าแก้ไฟล์ในโฟลเดอร์ `omr/` ให้หยุดแล้วรันใหม่
(Streamlit ไม่ reload โมดูลที่ import มา)

## 4. ไฟล์ตัวอย่างและโมเดล

```powershell
# กระดาษคำตอบสำหรับพิมพ์ (PDF + PNG) — ตั้งจำนวนข้อได้ 1–60
python tools/cli.py sheet --out samples/answer_sheet.pdf
python tools/cli.py sheet --out samples/answer_sheet_60.pdf --questions 60

# ภาพถ่ายสังเคราะห์ + เฉลย + ground truth สำหรับทดสอบ
python tools/synth.py --n 100 --out samples/synthetic --seed 42

# เทรน YOLOv8n (สร้างชุดข้อมูล label อัตโนมัติ + เทรน + คัดลอกโมเดลไป models/)
python tools/train_yolo.py
```

ถ้ามีไฟล์ `models/omr_problems_yolov8n.pt` อยู่แล้วไม่ต้องเทรนใหม่ ถ้าไม่มี ระบบยังทำงานได้ปกติ เพียงข้ามขั้น YOLO

## 5. ตรวจข้อสอบจาก command line (ไม่ต้องเปิดเว็บ)

```powershell
# ตรวจทั้งโฟลเดอร์ → Excel
python tools/cli.py grade samples/synthetic --key samples/synthetic/answer_key.csv --out results/results.xlsx

# บันทึกภาพ annotate และภาพทุกขั้นตอน (debug/<ชื่อไฟล์>/01_…06_….png)
python tools/cli.py grade photo.jpg --key key.csv --out out.xlsx --annotated results/annotated --debug
```

## 6. ทดสอบและวัดผล

```powershell
python -m pytest -q                                   # ทุกเทสต์ (~20 วินาที)
python -m pytest -q tests/test_extensions.py          # เฉพาะไฟล์
python -m pytest -q -k "paper_fallback"               # เฉพาะชื่อที่ตรง
python -m pytest -q -x                                # หยุดที่เทสต์แรกที่ล้ม

# accuracy + เวลา บนภาพสังเคราะห์ → reports/eval_YYYYMMDD_HHMM.md
python tools/evaluate.py --images samples/synthetic --truth samples/synthetic/ground_truth.csv

# ภาพถ่ายจริง (เตรียม ground_truth.csv เอง รูปแบบใน README)
python tools/evaluate.py --real --images real --truth real/ground_truth.csv --key real/answer_key.csv
```

ทุกครั้งที่รัน `evaluate.py` ระบบจะบันทึกเวอร์ชันและจำนวนความผิดพลาดลง `reports/history.csv`
แล้วแสดงตารางเทียบทุกเวอร์ชันพร้อม ★ เวอร์ชันที่ดีที่สุด

```powershell
python tools/evaluate.py --images samples/synthetic --truth samples/synthetic/ground_truth.csv --note "ปรับอะไร"
python tools/evaluate.py --history          # ดูตารางเทียบทุกเวอร์ชันโดยไม่ต้องรันใหม่
python tools/evaluate.py ... --no-history   # ทดลองชั่วคราว ไม่บันทึกประวัติ
```

**ก่อนส่งงานทุกครั้ง** ให้รัน `python -m pytest -q` และถ้าแก้ส่วนประมวลผลภาพ ให้รัน `tools/evaluate.py`
แล้วดูว่าเวอร์ชันใหม่ไม่แย่กว่าเดิม (โดยเฉพาะคอลัมน์ "ผิดโดยไม่เตือน") ขั้นตอนออกเวอร์ชันใหม่อยู่ท้าย
[CHANGELOG.md](CHANGELOG.md)

## 7. เทรน YOLOv8n ใหม่ / เพิ่มเติม

```powershell
python tools/train_yolo.py                              # ค่าเริ่มต้น 250/50 ภาพ, 30 epochs, imgsz 640 (CPU ~40 นาที)
python tools/train_yolo.py --n-train 400 --epochs 60    # ข้อมูลมากขึ้น เทรนนานขึ้น
python tools/train_yolo.py --generate-only              # สร้างชุดข้อมูลอย่างเดียว (datasets/omr_problems)
python tools/train_yolo.py --skip-generate              # เทรนจากชุดข้อมูลเดิม (เช่น หลังเพิ่มภาพจริงเข้าไปเอง)
python tools/train_yolo.py --questions 60               # กระดาษ 60 ข้อ
```

เพิ่มภาพจริง: วางภาพ **พื้นที่คำตอบที่ครอปแล้ว** ใน `datasets/omr_problems/images/train/` และไฟล์ label รูปแบบ YOLO
(`class cx cy w h` แบบ normalize, class 0 = multi_mark, 1 = faint_mark, 2 = erasure) ใน `labels/train/`
ชื่อเดียวกัน แล้วรัน `--skip-generate`

ถ้ามีการ์ดจอ NVIDIA: ติดตั้ง PyTorch รุ่น CUDA ตามคำสั่งที่ https://pytorch.org/get-started/locally/
แล้วเปลี่ยน `device="cpu"` ใน `tools/train_yolo.py` เป็น `device=0`

## 8. โครงสร้างโปรเจกต์ (จุดที่มักแก้)

```
app.py                 จุดเริ่มหน้าเว็บ: ตั้งค่าหน้า + st.navigation เปิดหน้าตาม URL
components/            หน้าเว็บ แยกโฟลเดอร์ละหนึ่งหน้า — แต่ละไฟล์คือหนึ่ง st.Page ที่มี URL ของตัวเอง
  dashboard/           หน้าหลัก     /               dashboard.py + dashboard.css
  upload/              อัปโหลดภาพ   /upload         upload.py
  result/              ผลการตรวจ    /result         result.py
  report/              รายงาน       /report         report.py
  export_excel/        ส่งออก Excel /export_excel   export_excel.py
  setting/             ตั้งค่า       /setting        setting.py
  sidebar/             เมนูด้านซ้าย       sidebar.py + sidebar.css
  shared/              ใช้ร่วมกันหลายหน้า: pages.py (ทะเบียนหน้า + go() เปลี่ยนหน้า),
                       state.py (session_state, ตรวจภาพ, บันทึก),
                       widgets.py (หัวเรื่อง, การ์ด KPI, ตาราง), styles.py + base.css
.streamlit/config.toml ธีมสี / ฟอนต์ / สี sidebar             ← เปลี่ยนสีทั้งระบบ
omr/config.py          ค่าคงที่ทั้งหมด (layout, threshold, YOLO) ← จูนค่า
omr/pipeline.py        grade_image(): รวมทุกขั้นตอน              ← เพิ่มขั้นตอนใหม่
omr/preprocess.py      OpenCV + imutils + SciPy + scikit-image
omr/reader.py          อ่าน bubble / ความมั่นใจ
omr/detector.py        YOLOv8n
omr/quality.py         เบลอ / มืด / แสงสะท้อน
omr/grader.py          ให้คะแนน, อ่านเฉลย CSV
omr/exporter.py        Excel (Pandas + OpenPyXL)
omr/storage.py         บันทึก/เปิดผลเป็นไฟล์ (แทนฐานข้อมูล)
omr/models.py          dataclass ผลลัพธ์ (SheetResult, QuestionResult, ProblemBox)
tools/                 cli.py, synth.py, evaluate.py, train_yolo.py
tests/                 pytest
models/                ไฟล์โมเดล YOLO
results/sessions/      ผลการตรวจที่บันทึก (session.json + results.xlsx + images/)
```

แนวทางเขียนโค้ดของโปรเจกต์:

- ตัวเลขทุกค่าอยู่ใน `omr/config.py` ห้ามใส่ตัวเลขลอย ๆ ในโมดูลอื่น
- `components/` เป็น UI อย่างเดียว งานประมวลผลอยู่ใน `omr/` (จึงเขียนเทสต์ได้โดยไม่ต้องเปิดเว็บ)
- แก้หน้าไหน แก้ในโฟลเดอร์ของหน้านั้น ของที่ใช้ตั้งแต่ 2 หน้าขึ้นไปย้ายไป `components/shared/`
- CSS ของหน้าใส่ไฟล์ `<ชื่อหน้า>.css` ข้าง `.py` แล้วเรียก `load_css(Path(__file__).with_name("<ชื่อ>.css"))` ใน `render()`
  (ไม่มีไฟล์ .html เพราะ Streamlit สร้าง HTML จากโค้ด Python ให้เอง)
- เพิ่มหน้าใหม่: สร้าง `components/<ชื่อ>/<ชื่อ>.py` ที่มี `render()` และท้ายไฟล์
  `if __name__ == "__main__": render()` แล้วเพิ่ม 1 แถวใน `PAGE_DEFS` ของ `components/shared/pages.py`
  หน้าจะเปิดได้ที่ `localhost:8501/<ชื่อ>` และขึ้นในเมนูอัตโนมัติ
- เปลี่ยนหน้าจากปุ่ม: `if st.button(...): go("result")` (จาก `components.shared.pages`) — ห้ามใช้เป็น `on_click`
- `grade_image()` ต้องไม่ raise — ความผิดพลาดใส่ใน `SheetResult.error` เป็นข้อความไทย
- เพิ่มฟิลด์ใน `SheetResult` แล้วต้องตรวจว่า `omr/storage.py` บันทึก/เปิดได้ (มีเทสต์ `test_session_roundtrip`)
- ข้อความที่ผู้ใช้เห็นเป็นภาษาไทย ข้อความที่วาดลงภาพด้วย OpenCV เป็นอังกฤษ (OpenCV วาดไทยไม่ได้)
- บันทึกการตัดสินใจที่ไม่ชัดเจนลง `DECISIONS.md`

## 9. ปัญหาที่พบบ่อย

| อาการ | วิธีแก้ |
|---|---|
| `ModuleNotFoundError` | ยังไม่ได้ activate venv → `.venv\Scripts\Activate.ps1` แล้ว `pip install -r requirements.txt` |
| หน้าตั้งค่าขึ้น "ไม่พบไฟล์โมเดล" | รัน `python tools/train_yolo.py` หรือคัดลอก `omr_problems_yolov8n.pt` ไปไว้ใน `models/` |
| แก้โค้ดใน `omr/` แล้วเว็บไม่เปลี่ยน | หยุด (`Ctrl + C`) แล้ว `streamlit run app.py` ใหม่ |
| พอร์ต 8501 ถูกใช้อยู่ | `streamlit run app.py --server.port 8600` |
| ติดตั้ง ultralytics/torch ช้าหรือล้ม | ติดตั้งแยกก่อน: `pip install torch --index-url https://download.pytorch.org/whl/cpu` แล้วค่อย `pip install -r requirements.txt` |
| ข้อความไทยใน PDF เป็นอังกฤษ | วางฟอนต์ `THSarabunNew.ttf` หรือ `Sarabun-Regular.ttf` ในโฟลเดอร์ `fonts/` แล้วสร้าง PDF ใหม่ |
| เทสต์ `test_app_*` ช้า | ปกติ (render หน้าเว็บจริงด้วย AppTest) รันเฉพาะไฟล์อื่นด้วย `-k "not app"` |
