"""Scout(X)のテスト。実APIは呼ばず、偽の応答で確認する。実行: python tests/test_scout_x.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import scout_x as s  # noqa: E402

# 1. example-* と不正なハンドルは除く
hs = s.handles([{"x_handle": "EXAMPLE_HANDLE_1"}, {"x_handle": "bic_akiba"}, {"x_handle": "@bad"}, {"x_handle": None}])
assert hs == ["bic_akiba"], hs

# 2. クエリは長さ上限内に分割され、返信とリポストを除外する
many = [f"shop_account_{i:03d}" for i in range(60)]
qs = s.build_queries(many)
assert len(qs) > 1 and all(len(q) <= 512 for q in qs), [len(q) for q in qs]
assert all("-is:retweet" in q and "-is:reply" in q for q in qs)
assert sum(q.count("from:") for q in qs) == 60

# 3. 新着の取得: since_id を渡し、URLを組み立てる
calls = []
def fake(url, token):
    calls.append(url)
    return {"data": [{"id": "105", "text": "抽選開始", "author_id": "1", "created_at": "2026-11-02T00:00:00Z"}],
            "includes": {"users": [{"id": "1", "username": "bic_akiba"}]}}
posts = s.fetch_new(["q"], "100", "TOKEN", get=fake)
assert posts[0]["url"] == "https://x.com/bic_akiba/status/105" and "since_id=100" in calls[0]

# 4. 削除確認: 返ってこなかったIDを削除として返す
def fake2(url, token):
    return {"data": [{"id": "1"}]}
assert s.find_deleted(["1", "2", "3"], "TOKEN", get=fake2) == ["2", "3"]
print("OK: scout_x テスト 4件")
