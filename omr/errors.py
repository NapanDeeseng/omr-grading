"""custom exceptions ของระบบ OMR (ข้อความเป็นภาษาไทยสำหรับแสดงผู้ใช้)"""

from __future__ import annotations


class OMRError(Exception):
    """ข้อผิดพลาดพื้นฐานของระบบ"""


class ImageLoadError(OMRError):
    """อ่านไฟล์ภาพไม่ได้ หรือชนิดไฟล์ไม่รองรับ"""


class MarkerNotFoundError(OMRError):
    """หามาร์กเกอร์มุมไม่ครบ 4 ตัว"""

    def __init__(self, found: int) -> None:
        self.found = found
        super().__init__(
            f"พบมาร์กเกอร์มุมกระดาษ {found} จาก 4 ตัว — "
            "คำแนะนำ: ถ่ายให้เห็นสี่เหลี่ยมดำทั้ง 4 มุมครบ, วางกระดาษบนพื้นสีเข้มที่ตัดกัน, "
            "เพิ่มแสงและหลีกเลี่ยงเงาทับมุมกระดาษ"
        )


class PaperNotFoundError(OMRError):
    """หาขอบกระดาษไม่พบ (ใช้เมื่อหามาร์กเกอร์ไม่ครบแล้วลองหาขอบกระดาษแทน)"""

    def __init__(self) -> None:
        super().__init__("หาขอบกระดาษไม่พบ — วางกระดาษบนพื้นสีเข้มที่ตัดกับกระดาษ และให้เห็นกระดาษครบทั้งแผ่น")


class AnswerKeyError(OMRError):
    """ไฟล์เฉลยไม่ถูกต้อง"""
