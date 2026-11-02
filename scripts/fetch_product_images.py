"""商品画像を取得元(img_url)から assets/products/ に保存する(D36)。
- 対象: img_url があり、img_file がまだ無い商品。
- 保存後に img_file を書き込む。取得に失敗した商品は変更しない(失敗の一覧を出す)。
- 画像は 800px 以下の webp に変換して保存する(Pillow)。
- 実行: python scripts/fetch_product_images.py [--limit N]
"""
import argparse
import io
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import products_lib  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
UA = "Mozilla/5.0 (compatible; pokeka-lottery-bot; +https://github.com/joe8210h-lgtm/pokeka-lottery)"


def download(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def to_webp(raw, max_w=800):
    from PIL import Image
    im = Image.open(io.BytesIO(raw))
    if im.mode in ("RGBA", "LA", "P"):
        im = im.convert("RGBA")
        bg = Image.new("RGB", im.size, (255, 255, 255))
        bg.paste(im, mask=im.split()[3])
        im = bg
    else:
        im = im.convert("RGB")
    if im.width > max_w:
        im = im.resize((max_w, round(im.height * max_w / im.width)), Image.LANCZOS)
    out = io.BytesIO()
    for q in (85, 75, 65, 55):
        out.seek(0); out.truncate()
        im.save(out, "WEBP", quality=q)
        if out.tell() <= products_lib.IMG_MAX_BYTES:
            break
    return out.getvalue()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()
    products = products_lib.load(ROOT)
    done, failed = [], []
    for p in products:
        if not p.get("img_url") or p.get("img_file"):
            continue
        if products_lib.check_image(p["img_url"], p.get("img_source")):
            failed.append((p["id"], "画像URLまたは出典が不正"))
            continue
        if a.limit and len(done) >= a.limit:
            break
        try:
            data = to_webp(download(p["img_url"]))
            rel = f"{products_lib.IMG_DIR}/{p['id']}.webp"
            (ROOT / rel).parent.mkdir(parents=True, exist_ok=True)
            (ROOT / rel).write_bytes(data)
            p["img_file"] = rel
            done.append(p["id"])
        except Exception as e:  # 取得失敗は変更しない
            failed.append((p["id"], type(e).__name__ + ": " + str(e)[:80]))
    products_lib.save(ROOT, products)
    print(f"保存 {len(done)}件 / 失敗 {len(failed)}件")
    for i, m in failed:
        print(f"  失敗 {i}: {m}")


if __name__ == "__main__":
    main()
