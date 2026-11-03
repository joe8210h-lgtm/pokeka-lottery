"""close_expired のテスト。実行: python tests/test_close_expired.py"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import close_expired as c  # noqa: E402

J = timezone(timedelta(hours=9))
now = datetime(2026, 11, 3, 12, 0, tzinfo=J)
items = [
    {"id": "a", "status": "open", "window_type": "fixed", "entry_end": "2026-11-03T11:59:00+09:00"},   # 終了 -> closed
    {"id": "b", "status": "open", "window_type": "fixed", "entry_end": "2026-11-03T12:01:00+09:00"},   # まだ -> 変更なし
    {"id": "c", "status": "open", "window_type": "rolling", "entry_end": "2026-01-01T00:00:00+09:00"},  # rolling -> 変更なし
    {"id": "d", "status": "upcoming", "window_type": "fixed", "entry_start": "2026-11-03T10:00:00+09:00", "entry_end": "2026-11-04T10:00:00+09:00"},  # -> open
    {"id": "e", "status": "upcoming", "window_type": "fixed", "entry_start": "2026-11-05T10:00:00+09:00", "entry_end": "2026-11-06T10:00:00+09:00"},  # 変更なし
    {"id": "f", "status": "unknown", "window_type": "fixed", "entry_end": None},  # 日付なし -> 変更なし
    {"id": "g", "status": "closed", "window_type": "fixed", "entry_end": "2026-12-01T00:00:00+09:00"},  # 既に closed -> 触らない
    {"id": "h", "status": "upcoming", "window_type": "fixed", "entry_start": "2026-10-01T00:00:00+09:00", "entry_end": "2026-10-02T00:00:00+09:00"},  # 開始も終了も過去 -> closed
    {"id": "i", "status": "open", "window_type": "fixed", "entry_end": "不正な日付"},  # 解析できない -> 変更なし
]
ch = c.update(items, now)
got = {i: n for i, _, n in ch}
assert got == {"a": "closed", "d": "open", "h": "closed"}, got
st = {x["id"]: x["status"] for x in items}
assert st["b"] == "open" and st["c"] == "open" and st["e"] == "upcoming" and st["f"] == "unknown" and st["g"] == "closed" and st["i"] == "open", st
assert c.update(items, now) == []  # 2回目は変更なし(べき等)
print("OK")
