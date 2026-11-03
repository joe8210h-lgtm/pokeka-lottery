"""data/shops.yaml から、画面用の data/shops.json を作る。
ブラウザは YAML を読めないため、画面で使う項目(地域の判定に必要なもの)だけを JSON にして出す。
Xのアカウント名・メモ・取得の優先度などは出さない。
使い方: python scripts/build_shops_json.py   (shops.yaml を変えたら実行し、shops.json も一緒にコミットする)
validate.py が、shops.json が shops.yaml と合っているかを検査する。
"""
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
FIELDS = ("id", "name", "chain_id", "store_type", "prefecture", "area")


def build():
    shops = yaml.safe_load((ROOT / "data/shops.yaml").read_text(encoding="utf-8"))["shops"]
    return [{k: s.get(k) for k in FIELDS} for s in shops]


def render(rows):
    return json.dumps(rows, ensure_ascii=False, indent=2) + "\n"


if __name__ == "__main__":
    (ROOT / "data/shops.json").write_text(render(build()), encoding="utf-8")
    print(f"data/shops.json を更新しました({len(build())}件)")
    sys.exit(0)
