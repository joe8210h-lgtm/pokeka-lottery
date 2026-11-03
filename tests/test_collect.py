"""collect.py のテスト(実通信なし・一時フォルダで実行)。実行: python tests/test_collect.py"""
import json
import shutil
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import collect as co  # noqa: E402

J = timezone(timedelta(hours=9))
NOW = datetime(2026, 11, 3, 12, 0, tzinfo=J)
OK_JSON = json.dumps({"product": "拡張パック「アビスアイ」", "entry_channel": "web_form", "window_type": "fixed",
                      "entry_start": "2026-11-04T10:00:00+09:00", "entry_end": "2026-11-06T23:59:00+09:00",
                      "confidence": 0.95}, ensure_ascii=False)


def mkroot(mode="measure", shadow=True, budget=100, kill=False):
    d = Path(tempfile.mkdtemp())
    (d / "data").mkdir()
    (d / "config").mkdir()
    for f in ("data/shops.yaml", "data/products.json", "data/lotteries.json"):
        shutil.copy(ROOT / f, d / f)
    (d / "data/lotteries.json").write_text("[]", encoding="utf-8")
    ops = yaml.safe_load((ROOT / "config/operations.yaml").read_text(encoding="utf-8"))
    ops["collection"]["mode"] = mode
    ops["safety"]["shadow_mode"], ops["safety"]["kill_switch"] = shadow, kill
    ops["budget"]["monthly_api_budget_yen"] = budget
    (d / "config/operations.yaml").write_text(yaml.safe_dump(ops, allow_unicode=True), encoding="utf-8")
    return d


def search_get(posts):
    def get(url, token):
        if "search/recent" in url:
            return {"data": [{"id": p[0], "text": p[1], "author_id": "u1"} for p in posts],
                    "includes": {"users": [{"id": "u1", "username": "bicikebukuro"}]}}
        return {"data": []}  # 削除確認: 何も生きていない
    return get


def lots(d):
    return json.loads((d / "data/lotteries.json").read_text(encoding="utf-8"))


E_ = {"X_BEARER_TOKEN": "dummy", "ANTHROPIC_API_KEY": "dummy"}
posts = [("100", "抽選A"), ("101", "抽選B"), ("102", "抽選C")]

# 1. 鍵なし・kill_switch は何もしない
r = co.run(mkroot(), {}, now=NOW)
assert r["skipped"] and "X_BEARER_TOKEN" in r["skipped"]
r = co.run(mkroot(kill=True), E_, now=NOW)
assert "kill_switch" in r["skipped"]

# 2. measure: 件数だけ数え、抽出せず、since_id を進める。本文はどこにも保存しない
d = mkroot("measure")
r = co.run(d, E_, get=search_get(posts), now=NOW)
assert r["posts"] == 3 and r["per_account"] == {"bicikebukuro": 3} and r["extracted"] == 0 and lots(d) == []
assert json.loads((d / "data/scout_state.json").read_text())["since_id"] == "102"
assert not any("抽選A" in p.read_text(encoding="utf-8") for p in d.rglob("*.json"))

# 3. extract + shadow_mode: 抽出して振り分けるが、公開データには書かない(記録は残る)
d = mkroot("extract", shadow=True)
r = co.run(d, E_, get=search_get(posts), client=lambda s, c: OK_JSON, now=NOW)
assert r["extracted"] == 3 and r["added"] == 0 and r["added_reason"] == "shadow_mode" and lots(d) == []
assert json.loads((d / "data/usage.json").read_text())["calls"] == 3

# 4. extract + 本番: 確認待ちとして追加される(抽出直後は consistency=unverified)。再実行しても重複しない
d = mkroot("extract", shadow=False)
r = co.run(d, E_, get=search_get(posts[:1]), client=lambda s, c: OK_JSON, now=NOW)
assert r["added"] == 1 and lots(d)[0]["review_needed"] is True and lots(d)[0]["source_grade"] == "store_notice"
d2 = d
(d2 / "data/scout_state.json").unlink()
r = co.run(d2, E_, get=search_get(posts[:1]), client=lambda s, c: OK_JSON, now=NOW)
assert r["duplicate"] == 1 and len(lots(d2)) == 1

# 5. 予算が途中で尽きたら、処理済みの最後の投稿IDまでしか進めない
d = mkroot("extract", shadow=True, budget=7)  # 1回3円 → 2回まで
r = co.run(d, E_, get=search_get(posts), client=lambda s, c: OK_JSON, now=NOW)
assert r["extracted"] == 2 and r["errors"], r
assert json.loads((d / "data/scout_state.json").read_text())["since_id"] == "101"

# 6. 予算0円なら extract は何も取得しない
r = co.run(mkroot("extract", budget=0), E_, get=search_get(posts), client=lambda s, c: OK_JSON, now=NOW)
assert r["skipped"] and r["posts"] == 0

# 7. 削除確認: 出典の投稿が消えたら review_needed=true、出典リンクを外す
d = mkroot("measure")
(d / "data/lotteries.json").write_text(json.dumps([{"id": "x1", "status": "open", "review_needed": False,
    "source_url": "https://x.com/bicikebukuro/status/555", "consistency": {"status": "match"}}]), encoding="utf-8")
r = co.run(d, E_, get=search_get([]), now=NOW)
it = lots(d)[0]
assert r["deleted"] == ["x1"] and it["source_url"] is None and it["review_needed"] and it["consistency"]["conflict_fields"] == ["source_deleted"]

# 8. 取得の失敗は errors に残し、since_id は進めない
def boom(url, token):
    raise OSError("x")
d = mkroot("measure")
r = co.run(d, E_, get=boom, now=NOW)
assert r["errors"] and not json.loads((d / "data/scout_state.json").read_text())["since_id"]
print("OK")
