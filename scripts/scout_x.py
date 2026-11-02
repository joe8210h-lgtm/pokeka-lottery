"""Scout(X): shops.yaml の公式アカウントの新着投稿だけを取得する。D39の条件に従う。

- 取得は前回以降の新着のみ(since_id)。状態は data/scout_state.json に保存する(投稿の全文は保存しない)。
- 投稿の全文は data/.inbox/ (gitignore)に置き、Extractorが項目化したら消す。リポジトリには入れない。
- 削除確認: 保存済みの投稿IDが取得できなくなったら「削除」として報告する(24時間以内に反映するため定期実行)。
- キーは環境変数 X_BEARER_TOKEN から読む。表示・ログには出さない。
使い方: python scripts/scout_x.py --dry-run   (APIを呼ばず、検索条件だけを表示)
"""
import argparse
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
STATE = ROOT / "data/scout_state.json"
INBOX = ROOT / "data/.inbox"
API = "https://api.x.com/2/tweets"
KEYWORDS = "(抽選 OR 予約 OR 応募 OR 受付 OR 販売)"
MAX_QUERY = 480  # 検索クエリの長さ上限(512)に余裕を持たせる


def handles(shops):
    """example-* と仮のハンドルを除いた、実在のハンドルを返す。"""
    out = []
    for s in shops:
        h = str(s.get("x_handle") or "")
        if h and not h.startswith("EXAMPLE_") and re.fullmatch(r"\w{1,15}", h):
            out.append(h)
    return out


def build_queries(hs):
    """アカウントを複数の検索に分ける。返信とリポストは除外する(取得件数=課金を減らす)。"""
    tail = f" {KEYWORDS} -is:retweet -is:reply"
    queries, cur = [], []
    for h in hs:
        trial = "(" + " OR ".join(f"from:{x}" for x in cur + [h]) + ")" + tail
        if cur and len(trial) > MAX_QUERY:
            queries.append("(" + " OR ".join(f"from:{x}" for x in cur) + ")" + tail)
            cur = [h]
        else:
            cur.append(h)
    if cur:
        queries.append("(" + " OR ".join(f"from:{x}" for x in cur) + ")" + tail)
    return queries


def load_state():
    if STATE.exists():
        return json.loads(STATE.read_text(encoding="utf-8"))
    return {"since_id": None, "last_run": None}


def http_get(url, token):
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def fetch_new(queries, since_id, token, get=http_get):
    """新着投稿を返す。since_id より新しいものだけ。getはテストで差し替える。"""
    posts = []
    for q in queries:
        params = {"query": q, "max_results": "100", "expansions": "author_id",
                  "tweet.fields": "created_at", "user.fields": "username"}
        if since_id:
            params["since_id"] = since_id
        data = get(f"{API}/search/recent?" + urllib.parse.urlencode(params), token)
        users = {u["id"]: u["username"] for u in data.get("includes", {}).get("users", [])}
        for t in data.get("data", []):
            posts.append({"id": t["id"], "text": t["text"], "created_at": t.get("created_at"),
                          "url": f"https://x.com/{users.get(t.get('author_id'), 'i')}/status/{t['id']}"})
    return posts


def find_deleted(post_ids, token, get=http_get):
    """保存済みの投稿IDのうち、取得できなくなったもの(削除・非公開・停止)を返す。"""
    gone = []
    ids = list(post_ids)
    for i in range(0, len(ids), 100):
        chunk = ids[i:i + 100]
        data = get(f"{API}?ids={','.join(chunk)}", token)
        alive = {t["id"] for t in data.get("data", [])}
        gone += [x for x in chunk if x not in alive]
    return gone


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="APIを呼ばず検索条件だけ表示")
    a = ap.parse_args()
    shops = yaml.safe_load((ROOT / "data/shops.yaml").read_text(encoding="utf-8"))["shops"]
    qs = build_queries(handles(shops))
    state = load_state()
    if a.dry_run or not qs:
        print(f"対象アカウント: {len(handles(shops))}件 / 検索: {len(qs)}回 / since_id: {state['since_id']}")
        for q in qs:
            print(" ", q)
        return 0
    token = os.environ.get("X_BEARER_TOKEN")
    if not token:
        print("X_BEARER_TOKEN が未設定です(GitHub Secretsに登録してください)", file=sys.stderr)
        return 1
    posts = fetch_new(qs, state["since_id"], token)
    INBOX.mkdir(parents=True, exist_ok=True)
    for p in posts:
        (INBOX / f"{p['id']}.json").write_text(json.dumps(p, ensure_ascii=False), encoding="utf-8")
    if posts:
        state["since_id"] = str(max(int(p["id"]) for p in posts))
    state["last_run"] = __import__("datetime").datetime.now().astimezone().isoformat(timespec="seconds")
    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"新着 {len(posts)}件(全文は data/.inbox/ に一時保存)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
