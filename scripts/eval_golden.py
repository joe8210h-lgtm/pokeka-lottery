"""正解データ(tests/golden/golden.json)で Extractor の精度を測る。
- 既定(モック): 期待値から作った「理想の応答」を返す偽のモデルで、測定の仕組み自体を確認する(費用ゼロ)。
- --live: 実際のモデルで測る(ANTHROPIC_API_KEY と予算が必要。予算0円なら呼ばない)。
合格率が config の golden_set.min_pass_rate 未満なら終了コード1(公開を止める目安)。
使い方: python scripts/eval_golden.py [--live]
"""
import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import extractor as ex  # noqa: E402
import publisher as pub  # noqa: E402

JST = timezone(timedelta(hours=9))
SHOP = {"id": "golden-shop", "name": "(架空)テスト店", "chain_id": None, "store_type": "local_shop"}
URL = "https://x.com/golden/status/1"
KEYS = ("method", "entry_channel", "window_type", "entry_start", "entry_end", "result_date", "announce_channel",
        "review_needed", "source_grade", "price_yen", "limit_per_person", "payment_restriction", "requirement_keys")


def actual(it, k):
    if k == "announce_channel":
        return it["announce"]["channel"]
    if k == "payment_restriction":
        return it["payment"]["restriction"]
    if k == "requirement_keys":
        return sorted(r["key"] for r in it["requirements"])
    return it.get(k)


def oracle(case):
    """期待値から、理想のモデル応答(JSON文字列)を作る。"""
    e = case["expected"]
    if e.get("non_lottery"):
        return json.dumps({"product": None, "confidence": 0})
    d = {"product": "(架空)商品", "confidence": 0.9 if not e.get("review_needed") else 0.5,
         "entry_channel": e.get("entry_channel"), "window_type": e.get("window_type", "fixed"),
         "entry_start": e.get("entry_start"), "entry_end": e.get("entry_end"), "result_date": e.get("result_date"),
         "announce_channel": e.get("announce_channel"), "price_yen": e.get("price_yen"),
         "limit_per_person": e.get("limit_per_person"), "payment_restriction": e.get("payment_restriction"),
         "requirements": [{"key": k, "label": k} for k in e.get("requirement_keys", [])]}
    if case["id"] == "golden-009":  # 矛盾した日付を、そのまま返すモデルを想定
        d["entry_start"], d["entry_end"] = "2026-11-15T00:00:00+09:00", "2026-11-13T00:00:00+09:00"
    return json.dumps(d, ensure_ascii=False)


def run(client_for_case, grade_for_case=lambda c: c["expected"].get("source_grade", "store_notice")):
    cases = json.loads((ROOT / "tests/golden/golden.json").read_text(encoding="utf-8"))["cases"]
    now = datetime(2026, 11, 3, 12, 0, tzinfo=JST)
    results = []
    for c in cases:
        e = c["expected"]
        it = ex.extract(c["input_text"], SHOP, URL, client_for_case(c), now=now, source_grade=grade_for_case(c))
        if e.get("non_lottery"):
            results.append((c["id"], it is None, [] if it is None else ["non_lottery"]))
            continue
        if it is None:
            results.append((c["id"], False, ["抽出できず"]))
            continue
        bad = [k for k in KEYS if k in e and actual(it, k) != (sorted(e[k]) if k == "requirement_keys" else e[k])]
        results.append((c["id"], not bad, bad))
    return results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true")
    a = ap.parse_args()
    ops = pub.load_ops()
    if a.live:
        month = datetime.now(JST).strftime("%Y-%m")
        ok, why = ex.within_budget({}, ops, month)
        if not ok:
            print(why)
            return 0
        cl = ex.AnthropicClient(ops["extractor"]["model"], ops["extractor"]["max_tokens"], ops["extractor"]["yen_per_call"])
        res = run(lambda c: (lambda s, content: cl(s, content)))
    else:
        res = run(lambda c: (lambda s, content: oracle(c)))
    passed = sum(1 for _, ok, _ in res if ok)
    for i, ok, bad in res:
        print(("OK  " if ok else "NG  ") + i + ("" if ok else f" 食い違い: {bad}"))
    rate = passed / len(res)
    need = ops["golden_set"]["min_pass_rate"]
    print(f"合格 {passed}/{len(res)} ({rate:.0%}) / 基準 {need:.0%}")
    return 0 if rate >= need else 1


if __name__ == "__main__":
    sys.exit(main())
