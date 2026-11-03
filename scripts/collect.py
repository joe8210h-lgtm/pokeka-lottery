"""収集の本体(定期実行から呼ぶ): Scout → Extractor → Publisher、削除確認、記録。
- mode=measure(既定): 新着の件数と費用だけを数える。抽出はしない。投稿の本文は保存しない。最初の1週間の試験用。
- mode=extract: 新着を抽出し、重複排除・振り分けして、安全装置(kill_switch/shadow_mode)を通ったものだけ書く。
- 投稿の全文はファイルに保存しない(D39①)。メモリ上だけで処理する。
- 抽出が予算などで途中で止まったら、処理済みの最後の投稿IDまでしか since_id を進めない(取りこぼし防止)。
- 削除確認(D39②): 保存済みのX出典の投稿が取得できなくなったら、review_needed=true にして出典リンクを外す。
- 条件が揃わなければ、何も取得せず理由を表示して正常終了する(鍵の未登録など)。
使い方: python scripts/collect.py [--root .]  環境変数: X_BEARER_TOKEN, ANTHROPIC_API_KEY(extractのとき)
"""
import argparse
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import extractor as ex  # noqa: E402
import publisher as pub  # noqa: E402
import scout_x as sc  # noqa: E402

JST = timezone(timedelta(hours=9))
X_ID = re.compile(r"^https://x\.com/[^/]+/status/(\d+)$")


def _load(p, default):
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default


def _save(p, v, nl="\n"):
    p.write_text(json.dumps(v, ensure_ascii=False, indent=2) + nl, encoding="utf-8")


def handle_of(url):
    m = re.match(r"^https://x\.com/([^/]+)/status/", url or "")
    return m.group(1).lower() if m else None


def mark_deleted(items, gone_ids, now):
    """削除された投稿が出典のものを、確認待ちにして出典リンクを外す。変更した id を返す。"""
    changed = []
    nows = now.strftime("%Y-%m-%dT%H:%M:00+09:00")
    for it in items:
        m = X_ID.match(it.get("source_url") or "")
        if m and m.group(1) in gone_ids:
            it["source_url"] = None
            it["review_needed"] = True
            it["consistency"] = {"status": "conflict", "checked_at": nows, "conflict_fields": ["source_deleted"]}
            changed.append(it["id"])
    return changed


def run(root, env, get=sc.http_get, client=None, now=None):
    root = Path(root)
    now = now or datetime.now(JST)
    ops = pub.load_ops(root)
    mode = ops["collection"].get("mode", "measure")
    rep = {"date": now.strftime("%Y-%m-%d %H:%M"), "mode": mode, "skipped": None, "posts": 0, "per_account": {},
           "extracted": 0, "publish": 0, "queue": 0, "discard": 0, "duplicate": 0, "added": 0, "added_reason": None,
           "deleted": [], "est_yen": 0.0, "errors": []}
    if ops["safety"].get("kill_switch"):
        rep["skipped"] = "kill_switch が有効です"
        return rep
    token = env.get("X_BEARER_TOKEN")
    if not token:
        rep["skipped"] = "X_BEARER_TOKEN が未設定です"
        return rep
    usage_p, state_p, log_p = root / "data/usage.json", root / "data/scout_state.json", root / "data/collect_log.json"
    month = now.strftime("%Y-%m")
    usage = _load(usage_p, {})
    if usage.get("month") != month:
        usage = {"month": month, "calls": 0, "est_yen": 0.0}
    if mode == "extract":
        if not env.get("ANTHROPIC_API_KEY") and client is None:
            rep["skipped"] = "ANTHROPIC_API_KEY が未設定です(extractモード)"
            return rep
        ok, why = ex.within_budget(usage, ops, month)
        if not ok:
            rep["skipped"] = why
            return rep
        client = client or ex.AnthropicClient(ops["extractor"]["model"], ops["extractor"]["max_tokens"], ops["extractor"]["yen_per_call"])

    shops = yaml.safe_load((root / "data/shops.yaml").read_text(encoding="utf-8"))["shops"]
    by_handle = {str(s["x_handle"]).lower(): s for s in shops if s["x_handle"] in sc.handles(shops)}
    qs = sc.build_queries(sc.handles(shops))
    state = _load(state_p, {"since_id": None, "last_run": None})
    lot_p = root / "data/lotteries.json"
    items = _load(lot_p, [])

    # 削除確認(先に行う。失敗しても収集は続ける)
    x_ids = [m.group(1) for it in items if it.get("status") != "closed" and (m := X_ID.match(it.get("source_url") or ""))]
    if x_ids:
        try:
            gone = set(sc.find_deleted(x_ids, token, get))
            rep["deleted"] = mark_deleted(items, gone, now)
        except Exception as e:  # noqa: BLE001
            rep["errors"].append(f"削除確認に失敗: {type(e).__name__}")

    try:
        posts = sorted(sc.fetch_new(qs, state["since_id"], token, get), key=lambda p: int(p["id"]))
    except Exception as e:  # noqa: BLE001
        rep["errors"].append(f"取得に失敗: {type(e).__name__}")
        _finish(rep, items, lot_p, log_p, usage_p, usage, state_p, state, now, changed=bool(rep["deleted"]))
        return rep
    rep["posts"] = len(posts)
    for p in posts:
        h = handle_of(p["url"])
        rep["per_account"][h or "?"] = rep["per_account"].get(h or "?", 0) + 1

    last_done, new_items = None, []
    if mode == "measure":
        last_done = posts[-1]["id"] if posts else None
    else:
        products = _load(root / "data/products.json", [])
        for p in posts:
            ok, why = ex.within_budget(usage, ops, month)
            if not ok:
                rep["errors"].append(why)
                break
            shop = by_handle.get(handle_of(p["url"]) or "")
            if shop is None:
                last_done = p["id"]
                continue
            try:
                it = ex.extract(p["text"], shop, p["url"], client, now=now, products=products)
            except Exception as e:  # noqa: BLE001  (1件の失敗で全体を止めない。次回は同じ投稿から再取得する)
                rep["errors"].append(f"抽出に失敗: {type(e).__name__}")
                break
            usage["calls"] += 1
            usage["est_yen"] = round(usage["est_yen"] + ops["extractor"]["yen_per_call"], 2)
            rep["est_yen"] += ops["extractor"]["yen_per_call"]
            last_done = p["id"]
            if it:
                rep["extracted"] += 1
                new_items.append(it)
        res = pub.plan(new_items, items, ops)
        for k in ("publish", "queue", "discard", "duplicate"):
            rep[k] = len(res[k])
        items, n, why = pub.apply(res, items, ops)
        rep["added"], rep["added_reason"] = n, why

    if last_done:
        state["since_id"] = last_done
    _finish(rep, items, lot_p, log_p, usage_p, usage, state_p, state, now, changed=True)
    return rep


def _finish(rep, items, lot_p, log_p, usage_p, usage, state_p, state, now, changed):
    if changed:
        _save(lot_p, items, nl="")  # lotteries.json は末尾に改行を付けない(既存の形式)
    state["last_run"] = now.isoformat(timespec="seconds")
    _save(state_p, state)
    _save(usage_p, usage)
    log = _load(log_p, [])
    log.append({k: v for k, v in rep.items() if k != "skipped"})
    _save(log_p, log[-60:])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=str(Path(__file__).resolve().parent.parent))
    a = ap.parse_args()
    rep = run(a.root, os.environ)
    print(json.dumps(rep, ensure_ascii=False))
    if rep["skipped"]:
        print("収集をスキップ: " + rep["skipped"])
        return 0
    return 1 if rep["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
