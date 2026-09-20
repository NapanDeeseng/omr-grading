"""ไอคอนเส้น (outline) 24×24 สำหรับฝังใน HTML ของการ์ด/ป้ายสถานะ — สีตาม currentColor

ปุ่ม/เมนู/หัวข้อที่เป็น widget ของ Streamlit ให้ใช้ Material Symbols (":material/ชื่อ:") แทน
"""

from __future__ import annotations

_PATHS: dict[str, str] = {
    # บัตรนักเรียน
    "id_card": '<rect x="3" y="5" width="18" height="14" rx="2.5"/><circle cx="9" cy="11" r="2"/>'
               '<path d="M6 16.2c.7-1.3 1.8-2 3-2s2.3.7 3 2M14.5 10h4M14.5 13.5h3"/>',
    # กระดาษคำตอบที่ตรวจแล้ว
    "score": '<rect x="5" y="4" width="14" height="17" rx="2.5"/><rect x="9" y="2.5" width="6" height="3.5" rx="1"/>'
             '<path d="m8.8 13.2 2.3 2.3 4.4-4.6"/>',
    # ความมั่นใจ
    "shield": '<path d="M12 3 19 6v5.2c0 4.3-2.9 8-7 9.3-4.1-1.3-7-5-7-9.3V6z"/><path d="m9 12 2.1 2.1L15.2 10"/>',
    # ต้องตรวจสอบ
    "alert": '<path d="M10.3 4.3 2.9 17.5A2 2 0 0 0 4.6 20.5h14.8a2 2 0 0 0 1.7-3L13.7 4.3a2 2 0 0 0-3.4 0z"/>'
             '<path d="M12 9.5v4M12 17h.01"/>',
    # จำนวนแผ่น
    "sheets": '<path d="M8 7V5a2 2 0 0 1 2-2h7l3 3v10a2 2 0 0 1-2 2h-2"/>'
              '<rect x="4" y="7" width="12" height="14" rx="2"/><path d="M7.5 12h5M7.5 15.5h5"/>',
    # คะแนนเฉลี่ย
    "chart": '<path d="M4 20h16M7 16.5v-5M12 16.5V7M17 16.5v-8"/>',
    # ป้ายสถานะ
    "check": '<circle cx="12" cy="12" r="9"/><path d="m8.5 12.2 2.4 2.4 4.6-4.8"/>',
    "cross": '<circle cx="12" cy="12" r="9"/><path d="m9.2 9.2 5.6 5.6M14.8 9.2l-5.6 5.6"/>',
    # โลโก้: กระดาษคำตอบที่มีวงฝน
    "logo": '<rect x="4" y="3" width="16" height="18" rx="2.5"/><circle cx="9" cy="9" r="1.7" fill="currentColor"/>'
            '<circle cx="15" cy="9" r="1.7"/><circle cx="9" cy="15" r="1.7"/>'
            '<circle cx="15" cy="15" r="1.7" fill="currentColor"/>',
}


def svg(name: str, size: int = 24, stroke: float = 1.8) -> str:
    """คืน <svg> ของไอคอนตามชื่อ (ดูชื่อได้ใน _PATHS)"""
    return (f'<svg viewBox="0 0 24 24" width="{size}" height="{size}" fill="none" stroke="currentColor" '
            f'stroke-width="{stroke}" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
            f'{_PATHS[name]}</svg>')
