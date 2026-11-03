"""Publisher: 抽出した抽選を、重複排除し、確信度で振り分ける。公開データへの書き込みは、安全装置を通ったときだけ。
- 振り分け(config/operations.yaml の閾値): 自動公開 / 確認待ち / 破棄。validate.py と同じ規則。
- 重複: 同じ店舗・同じ商品・同じ受付期間は1件にまとめる(CLAUDE.md)。既存を優先し、上書きしない。
- 安全装置: kill_switch が true なら何も書かない。shadow_mode が true の間は、公開データに書かず、結果の件数だけを返す。
- 確認待ちの項目は、review_needed=true で出す(人が見てから公開する)。破棄は書かない。
実行はライブラリとして使う(収集の定期実行から呼ぶ)。単体: python scripts/publisher.py items.json
"""
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent


def load_ops(root=ROOT):
    return yaml.safe_load((Path(root) / "config/operations.yaml").read_text(encoding="utf-8"))


def classify(it, ops):
    pp = ops["publish_policy"]
    q, a = pp["queue_min_confidence"], pp["auto_publish_min_confidence"]
    status = (it.get("consistency") or {}).get("status", "unverified")
    conf = it.get("confidence", 0)
    if it.get("review_needed") or status != "match":
        return "queue" if conf >= q else "discard"
    return "publish" if conf >= a else ("queue" if conf >= q else "discard")


def dup_key(it):
    return (it.get("shop_id"), (it.get("product") or "").strip(), it.get("entry_start"), it.get("entry_end"))


def plan(new_items, existing, ops):
    """{'publish': [...], 'queue': [...], 'discard': [...], 'duplicate': [...]} を返す。"""
    seen = {dup_key(x) for x in existing}
    ids = {x.get("id") for x in existing}
    out = {"publish": [], "queue": [], "discard": [], "duplicate": []}
    for it in new_items:
        k = dup_key(it)
        if k in seen or it.get("id") in ids:
            out["duplicate"].append(it)
            continue
        seen.add(k)
        out[classify(it, ops)].append(it)
    return out


def apply(result, existing, ops):
    """安全装置を通して、追加する項目を決める。(追加後の全件, 追加した件数, 理由) を返す。"""
    s = ops["safety"]
    if s.get("kill_switch"):
        return existing, 0, "kill_switch"
    if s.get("shadow_mode"):
        return existing, 0, "shadow_mode"
    add = list(result["publish"])
    for it in result["queue"]:
        add.append({**it, "review_needed": True})  # 確認待ちは、必ず人の確認つきで出す
    return existing + add, len(add), "applied"


def main():
    items = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    ops = load_ops()
    path = ROOT / "data/lotteries.json"
    existing = json.loads(path.read_text(encoding="utf-8"))
    res = plan(items, existing, ops)
    merged, n, why = apply(res, existing, ops)
    print(json.dumps({k: len(v) for k, v in res.items()} | {"added": n, "reason": why}, ensure_ascii=False))
    if n:
        path.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
