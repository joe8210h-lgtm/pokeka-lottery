"""X投稿の取り込みIssueの本文を読み取り、項目に分けて確認用のJSONを作る。
公開データは変更しない(読み取りと検査だけ)。入力はIssueの本文(テキスト)。
使い方: python scripts/parse_intake.py issue_body.txt
"""
import json
import re
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import products_lib  # noqa: E402

LABELS = {
    "店舗名": "store_name",
    "投稿のURL": "post_url",
    "商品名": "product",
    "商品画像のURL": "img_url",
    "画像の出典URL": "img_source",
    "受付方法": "entry_channel",
    "受付開始(日本時間)": "entry_start",
    "受付終了(日本時間)": "entry_end",
    "当選発表日": "result_date",
    "必要なもの(短く)": "requirements",
    "支払いの制限": "payment",
    "確認状況": "verified",
}
CHANNEL_MAP = {
    "店頭": "in_store", "Webフォーム": "web_form", "Xリポスト": "x_repost",
    "アプリ": "app", "招待リクエスト": "invitation", "不明": "unknown",
}
PAYMENT_MAP = {"なし": "none", "指定カードのみ": "own_card_only", "不明": "unknown"}
EMPTY = {"", "_No response_"}


def parse_sections(body):
    """### 見出し ごとに本文を取り出す。"""
    out = {}
    parts = re.split(r"^### (.+)$", body, flags=re.M)
    for i in range(1, len(parts), 2):
        label = parts[i].strip()
        value = parts[i + 1].strip() if i + 1 < len(parts) else ""
        out[label] = value
    return out


def to_iso(v):
    """'2026-10-27 10:00' を '2026-10-27T10:00:00+09:00' にする。空や不正は None。"""
    if v in EMPTY:
        return None, None
    for fmt, out in (("%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:00+09:00"), ("%Y-%m-%d", "%Y-%m-%dT00:00:00+09:00")):
        try:
            return datetime.strptime(v, fmt).strftime(out), None
        except ValueError:
            continue
    return None, f"日時の形式が不正です: {v}(例: 2026-10-27 10:00)"


def parse(body):
    sec = parse_sections(body)
    data, errors, warnings = {}, [], []
    for label, key in LABELS.items():
        raw = next((v for h, v in sec.items() if h.startswith(label)), "")
        data[key] = None if raw in EMPTY else raw
    data.pop("verified", None)

    if not data["store_name"]:
        errors.append("店舗名がありません")
    if not data["post_url"] or not str(data["post_url"]).startswith("https://"):
        errors.append("投稿のURLがhttpsで始まっていません")
    ch = data["entry_channel"]
    data["entry_channel"] = CHANNEL_MAP.get(ch, "unknown")
    if data["entry_channel"] == "unknown":
        warnings.append("受付方法が不明です")
    data["payment_restriction"] = PAYMENT_MAP.get(data.pop("payment") or "不明", "unknown")

    for key in ("entry_start", "entry_end", "result_date"):
        iso, err = to_iso(data[key] or "")
        data[key] = iso
        if err:
            errors.append(err)
    if data["entry_end"] is None:
        warnings.append("受付終了が不明です(確認待ちになります)")
    if not data["product"]:
        warnings.append("商品名が未入力です")
    errors.extend(products_lib.check_image(data["img_url"], data["img_source"]))
    if data["product"] and not data["img_url"]:
        warnings.append("商品画像が未入力です(商品マスターに画像がなければ、仮イラストで表示します)")
    if data["payment_restriction"] == "unknown":
        warnings.append("支払いの制限が「不明」または未選択です。支払い条件を確認してください")

    req = [r.strip("- ").strip() for r in (data["requirements"] or "").splitlines() if r.strip()]
    data["requirements_hint"] = [{"key": "hint", "label": r[:40]} for r in req]
    data["requirements"] = None

    data["verified_by_human"] = any("[x]" in v for h, v in sec.items() if h.startswith("確認状況"))
    data["source_grade"] = "third_party"
    data["review_needed"] = True  # 取り込みの段階では、必ず確認待ち
    data["status"] = "unknown" if data["entry_end"] is None else "upcoming"
    return {"data": data, "errors": errors, "warnings": warnings}


if __name__ == "__main__":
    body = open(sys.argv[1], encoding="utf-8").read()
    print(json.dumps(parse(body), ensure_ascii=False, indent=2))
