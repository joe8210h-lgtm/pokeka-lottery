"""check_links のテスト(実通信なし)。実行: python tests/test_check_links.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import check_links as c  # noqa: E402

items = [
    {"id": "sample-1", "status": "open", "source_url": "https://x.example/sample"},          # サンプルは対象外
    {"id": "a", "status": "open", "source_url": "https://ok.example/1", "apply_url": "https://gone.example/2"},
    {"id": "b", "status": "closed", "source_url": "https://gone.example/3"},                  # closed は対象外
    {"id": "c", "status": "upcoming", "source_url": "https://bot.example/4"},                 # 403 は切れ扱いにしない
    {"id": "d", "status": "open", "source_url": "https://down.example/5"},                    # 接続失敗は切れ
    {"id": "e", "status": "open", "source_url": "https://ok.example/1"},                      # 同URLは1回だけ取得
]
calls = []
resp = {"https://ok.example/1": 200, "https://gone.example/2": 404, "https://bot.example/4": 403, "https://down.example/5": "ERR:URLError"}


def fake(u):
    calls.append(u)
    return resp[u]


broken, n = c.check(items, fake)
assert [(i, k) for i, k, _, _ in broken] == [("a", "apply_url"), ("d", "source_url")], broken
assert n == 4 and len(calls) == 4, (n, calls)
print("OK")
