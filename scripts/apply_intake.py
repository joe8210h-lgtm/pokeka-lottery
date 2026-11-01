"""承認済み(approved ラベル)のX取込Issueを、公開データ(lotteries.json)に追加する。
直接mainには書かない。追加後のファイルを、workflowがブランチとPRにする。マージした人が公開を決める。
使い方: python scripts/apply_intake.py 本文ファイル --issue 番号 [--root リポジトリの場所]
終了コード: 0=追加した / 1=拒否(理由を標準出力のJSONに出す)
"""
import argparse
import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from parse_intake import parse  # noqa: E402

JST = timezone(timedelta(hours=9))
METHOD = {"in_store": "store", "web_form": "online", "x_repost": "online",
          "app": "online", "invitation": "online", "unknown": "unknown"}


def reject(reasons):
    print(json.dumps({"status": "rejected", "reasons": reasons}, ensure_ascii=False))
    return 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("body")
    ap.add_argument("--issue", required=True, type=int)
    ap.add_argument("--root", default=".")
    a = ap.parse_args()
    root = Path(a.root)

    result = parse(open(a.body, encoding="utf-8").read())
    d, reasons = result["data"], list(result["errors"])

    if not d["verified_by_human"]:
        reasons.append("「確認状況」にチェックがありません(店舗の公式情報で確認してから承認してください)")
    if not d["entry_end"]:
        reasons.append("受付終了が不明なので、承認できません")
    if not d["product"]:
        reasons.append("商品名が未入力です")

    shops = yaml.safe_load((root / "data/shops.yaml").read_text(encoding="utf-8"))["shops"]
    shop = next((s for s in shops if s.get("name", "").strip() == (d["store_name"] or "").strip()), None)
    if shop is None:
        reasons.append("店舗名が店舗リスト(data/shops.yaml)に一致しません。先に店舗を登録してください")

    path = root / "data/lotteries.json"
    items = json.loads(path.read_text(encoding="utf-8"))
    new_id = f"x-{a.issue}"
    if any(i.get("id") == new_id for i in items):
        reasons.append(f"同じID({new_id})が既にあります")

    if reasons:
        return reject(reasons)

    now = datetime.now(JST).strftime("%Y-%m-%dT%H:%M:00+09:00")
    start, end = d["entry_start"], d["entry_end"]
    nowdt = datetime.now(JST)
    status = "upcoming" if start and datetime.fromisoformat(start) > nowdt else "open"
    item = {
        "id": new_id,
        "shop_id": shop["id"],
        "shop_name": shop["name"],
        "chain_id": shop.get("chain_id"),
        "store_type": shop.get("store_type", "local_shop"),
        "product": d["product"],
        "method": METHOD.get(d["entry_channel"], "unknown"),
        "entry_channel": d["entry_channel"],
        "window_type": "fixed",
        "entry_start": start,
        "entry_end": end,
        "result_date": d["result_date"],
        "announce": {"channel": "x_post", "no_inquiry": False},
        "purchase_start": None,
        "purchase_end": None,
        "delivery": "unknown",
        "shrink": "unknown",
        "limit_per_person": None,
        "requirements": [{"key": "hint", "label": r["label"]} for r in d["requirements_hint"]],
        "payment": {"restriction": d["payment_restriction"], "required_card": None, "timing": "unknown"},
        "may_close_early": False,
        "exclusive_group": None,
        "status": status,
        "source_type": "x",
        "source_grade": "store_notice",
        "source_url": d["post_url"],
        "first_seen_at": now,
        "last_verified_at": now,
        "confidence": 0.95,
        "review_needed": False,
        "consistency": {"status": "match", "checked_at": now, "conflict_fields": []},
    }
    items.append(item)
    path.write_text(json.dumps(items, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "added", "id": new_id, "shop_name": shop["name"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
