"""掲載中(open/upcoming)の抽選の出典・応募先リンクが生きているかを調べる。1日1回、各URLに1リクエストだけ。
実行: python scripts/check_links.py [--out report.md]
リンク切れ(404/410・接続失敗)があれば、--out にMarkdownの報告を書き、終了コード2で終わる。
403/429などの「機械お断り」は切れと見なさない(人の確認待ち扱いにはしない)。サンプル(id が sample- 始まり)は調べない。"""
import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data" / "lotteries.json"
UA = "pokeka-lottery-linkcheck/1.0"
BROKEN_CODES = {404, 410}


def fetch_status(url, timeout=15):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception as e:  # 接続失敗・DNS・タイムアウト
        return f"ERR:{type(e).__name__}"


def targets(items):
    out = []
    for it in items:
        if it.get("status") not in ("open", "upcoming") or str(it.get("id", "")).startswith("sample"):
            continue
        for key in ("source_url", "apply_url"):
            u = it.get(key)
            if u and u.startswith(("http://", "https://")):
                out.append((it["id"], key, u))
    return out


def check(items, fetch=fetch_status):
    broken = []
    seen = {}
    for i, key, u in targets(items):
        if u not in seen:
            seen[u] = fetch(u)
        s = seen[u]
        if s in BROKEN_CODES or (isinstance(s, str) and s.startswith("ERR:")):
            broken.append((i, key, u, s))
    return broken, len(seen)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out")
    a = ap.parse_args()
    items = json.loads(DATA.read_text(encoding="utf-8"))
    broken, n = check(items)
    print(f"確認したURL {n}件 / リンク切れ {len(broken)}件")
    if broken:
        lines = ["掲載中の抽選のリンク切れを検知しました。店舗の告知が削除・移動された可能性があります。確認して、出典を直すか、抽選を closed にしてください。", ""]
        lines += [f"- {i} の {k}: {u} ({s})" for i, k, u, s in broken]
        print("\n".join(lines))
        if a.out:
            Path(a.out).write_text("\n".join(lines) + "\n", encoding="utf-8")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
