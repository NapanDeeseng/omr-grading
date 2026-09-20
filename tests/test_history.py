"""ทดสอบประวัติเวอร์ชันของ evaluate: นับความผิดพลาด และเลือกเวอร์ชันที่ดีที่สุด"""

from __future__ import annotations

from pathlib import Path

import evaluate as E


def _row(version: str, q_wrong: int, silent: str, flagged: str = "100", ms: str = "50", detected: int = 100,
         id_wrong: int = 0) -> dict[str, str]:
    return {"version": version, "date": "2026-01-01", "mode": "synthetic", "images": "synthetic", "sheets": "100",
            "detected": str(detected), "q_total": "4000", "q_wrong": str(q_wrong), "q_wrong_silent": silent,
            "id_wrong": str(id_wrong), "id_wrong_silent": "0", "flagged": flagged, "mean_ms": ms, "p95_ms": ms,
            "note": ""}


def test_error_counts() -> None:
    r = _row("1", q_wrong=3, silent="1", detected=98, id_wrong=2)
    assert E.total_errors(r) == 3 + 2 + 2
    assert E.silent_errors(r) == 1 + 0 + 2
    assert E.silent_errors(_row("x", 6, "")) == 6  # ไม่ทราบว่าเตือนไหม ถือว่าไม่เตือน


def test_best_version_prefers_fewest_silent_errors() -> None:
    v10, v11, v12 = _row("1.0", 6, ""), _row("1.1", 1, "1", "166", "58"), _row("1.2", 1, "0", "382", "330")
    assert E.best_row([v10, v11, v12]) is v12          # ผิดเท่ากันแต่ 1.2 เตือนครบ
    assert E.best_row([v10, v11]) is v11               # ผิดน้อยกว่า
    fast = _row("1.3", 1, "0", "382", "100")
    assert E.best_row([v12, fast]) is fast             # เท่ากันหมด เลือกตัวที่เร็วกว่า
    assert E.best_row([]) is None


def test_history_append_and_table(tmp_path: Path) -> None:
    path = tmp_path / "history.csv"
    E.append_history(path, _row("1.0", 6, ""))
    E.append_history(path, _row("1.1", 1, "1"))
    rows = E.load_history(path)
    assert [r["version"] for r in rows] == ["1.0", "1.1"]
    table = E.history_table(rows)
    assert "★ | 1.1" in table and "★ | 1.0" not in table
