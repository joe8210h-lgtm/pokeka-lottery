"""商品マスター(data/products.json)の共通処理。商品名と画像を紐づけて管理する(D31)。
画像は assets/products/ に保存して自サイトから出す(D36。D32の「URLだけ」を変更)。img_url は取得元、img_file は保存先。
X投稿の画像は使わない。出典ページのURLを必ず記録する。
"""
import json
import re
import unicodedata
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.parse import urlparse

JST = timezone(timedelta(hours=9))
# X投稿の画像(x.com / twitter.com / twimg.com)は、X規約と権利の面で使わない
BLOCKED_IMG_HOSTS = ("x.com", "twitter.com", "twimg.com", "t.co")


def norm(s):
    """表記ゆれをならして比較用の文字列にする(全角半角、空白、かぎ括弧、大文字小文字)。"""
    s = unicodedata.normalize("NFKC", s or "")
    s = re.sub(r"[\s「」『』\[\]()（）【】・\-]", "", s)
    return s.casefold()


def host_blocked(url):
    h = (urlparse(url).hostname or "").lower()
    return any(h == b or h.endswith("." + b) for b in BLOCKED_IMG_HOSTS)


def check_image(img_url, img_source):
    """画像URLと出典の検査。問題の文章のリストを返す(空なら問題なし)。"""
    errs = []
    if not img_url and not img_source:
        return errs
    if bool(img_url) != bool(img_source):
        errs.append("画像のURLと出典のURLは、2つそろえて入力してください")
        return errs
    for label, u in (("画像のURL", img_url), ("画像の出典URL", img_source)):
        if not str(u).startswith("https://"):
            errs.append(f"{label}がhttpsで始まっていません")
        elif host_blocked(u):
            errs.append(f"{label}にXの投稿・画像は使えません(D31)。商品の公式・販売店のページのものを使ってください")
    return errs


IMG_DIR = "assets/products"
IMG_EXT = (".webp", ".jpg", ".jpeg", ".png")
IMG_MAX_BYTES = 400 * 1024


def check_file(root, img_file):
    """保存した画像ファイルの検査。問題の文章のリストを返す(空なら問題なし)。"""
    if not img_file:
        return []
    f = str(img_file)
    if not f.startswith(IMG_DIR + "/") or ".." in f or not f.lower().endswith(IMG_EXT):
        return [f"画像ファイルは {IMG_DIR}/ 内の webp/jpg/png にしてください: {f}"]
    p = Path(root) / f
    if not p.is_file():
        return [f"画像ファイルが見つかりません: {f}"]
    if p.stat().st_size > IMG_MAX_BYTES:
        return [f"画像ファイルが大きすぎます(400KB以下): {f}"]
    return []


def load(root):
    p = Path(root) / "data/products.json"
    return json.loads(p.read_text(encoding="utf-8"))


def save(root, products):
    p = Path(root) / "data/products.json"
    p.write_text(json.dumps(products, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def find(products, name):
    """商品名(または別名)に一致する商品を返す。なければ None。"""
    key = norm(name)
    if not key:
        return None
    for p in products:
        if key in {norm(p.get("name"))} | {norm(a) for a in p.get("aliases", [])}:
            return p
    return None


def next_id(products):
    n = max([int(m.group(1)) for p in products if (m := re.fullmatch(r"p-(\d+)", p.get("id", "")))] or [0])
    return f"p-{n + 1}"


def today():
    return datetime.now(JST).strftime("%Y-%m-%d")
