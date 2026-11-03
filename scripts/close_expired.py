"""受付期間を過ぎた抽選を closed にし、受付が始まった upcoming を open にする(削除はしない)。
実行: python scripts/close_expired.py [--now 2026-11-03T12:00:00+09:00] [--dry-run]
変更があれば終了コード0で件数を表示する。window_type が rolling のものは、終了日で閉じない。"""
import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

JST = timezone(timedelta(hours=9))
DATA = Path(__file__).resolve().parent.parent / "data" / "lotteries.json"


def parse(s):
    if not s:
        return None
    try:
        d = datetime.fromisoformat(s)
    except ValueError:
        return None
    return d if d.tzinfo else d.replace(tzinfo=JST)


def update(items, now):
    """items を直接更新し、[(id, 旧status, 新status)] を返す。"""
    changes = []
    for it in items:
        st = it.get("status")
        if st == "closed":
            continue
        start, end = parse(it.get("entry_start")), parse(it.get("entry_end"))
        new = st
        if it.get("window_type") != "rolling" and end and end < now:
            new = "closed"
        elif st == "upcoming" and start and start <= now and (not end or now <= end):
            new = "open"
        if new != st:
            it["status"] = new
            changes.append((it.get("id"), st, new))
    return changes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--now")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    now = parse(a.now) if a.now else datetime.now(JST)
    items = json.loads(DATA.read_text(encoding="utf-8"))
    ch = update(items, now)
    for i, o, n in ch:
        print(f"{i}: {o} -> {n}")
    print(f"変更 {len(ch)}件")
    if ch and not a.dry_run:
        DATA.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
