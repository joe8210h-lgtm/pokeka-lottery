"""data/ と config/ の整合性を検証し、公開の振り分けを集計する。GitHub Actions から自動実行される。失敗すると終了コード1。"""
import json
import os
import sys
from datetime import datetime
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import products_lib  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
errors = []
warnings = []

schema = json.loads((ROOT / "data/schema.json").read_text(encoding="utf-8"))
items = json.loads((ROOT / "data/lotteries.json").read_text(encoding="utf-8"))
chains = yaml.safe_load((ROOT / "data/chains.yaml").read_text(encoding="utf-8"))["chains"]
shops = yaml.safe_load((ROOT / "data/shops.yaml").read_text(encoding="utf-8"))["shops"]
ops = yaml.safe_load((ROOT / "config/operations.yaml").read_text(encoding="utf-8"))
golden = json.loads((ROOT / "tests/golden/golden.json").read_text(encoding="utf-8"))
chain_ids = {c["id"] for c in chains}
shop_ids = {s["id"] for s in shops}
products = json.loads((ROOT / "data/products.json").read_text(encoding="utf-8"))
product_ids = {p.get("id") for p in products}

try:
    import jsonschema
except ImportError:
    jsonschema = None
    if os.environ.get("CI"):
        errors.append("jsonschema が未導入です")
    else:
        print("注意: jsonschema 未導入のため、スキーマ検証はスキップします")


def parse(v):
    return datetime.fromisoformat(v) if v else None


# --- 設定値の妥当性 ---
pp = ops["publish_policy"]
q, a = pp["queue_min_confidence"], pp["auto_publish_min_confidence"]
if not (0 < q < a <= 1):
    errors.append(f"config: 閾値の順序が不正です(queue={q}, auto={a})")
if ops["safety"]["shadow_mode"] and ops["safety"]["kill_switch"]:
    warnings.append("shadow_mode と kill_switch が両方有効です")
if ops["budget"]["monthly_api_budget_yen"] == 0:
    warnings.append("API予算が0円です(無料の試験運用)")


def classify(it):
    """公開の振り分け: publish / queue / discard"""
    c = it.get("consistency") or {}
    status = c.get("status", "unverified")
    conf = it.get("confidence", 0)
    if it.get("review_needed") or status != "match":
        return "queue" if conf >= q else "discard"
    if conf >= a:
        return "publish"
    return "queue" if conf >= q else "discard"


# --- 抽選データ ---
seen = set()
band = {"publish": 0, "queue": 0, "discard": 0}
for it in items:
    i = it.get("id", "(idなし)")
    if jsonschema:
        try:
            jsonschema.validate(it, schema)
        except jsonschema.ValidationError as e:
            errors.append(f"{i}: スキーマ違反: {e.message}")
    if i in seen:
        errors.append(f"{i}: idが重複しています")
    seen.add(i)
    if it.get("shop_id") not in shop_ids:
        errors.append(f"{i}: shop_id '{it.get('shop_id')}' が shops.yaml にありません")
    if it.get("chain_id") and it["chain_id"] not in chain_ids:
        errors.append(f"{i}: chain_id '{it['chain_id']}' が chains.yaml にありません")
    for k in ("entry_start", "entry_end", "result_date", "purchase_start", "purchase_end", "first_seen_at", "last_verified_at"):
        try:
            parse(it.get(k))
        except ValueError:
            errors.append(f"{i}: {k} が日時として読めません")
    try:
        s, e = parse(it.get("entry_start")), parse(it.get("entry_end"))
        if s and e and e < s:
            errors.append(f"{i}: 受付終了が開始より前です")
    except ValueError:
        pass
    if not it.get("entry_end") and not it.get("review_needed"):
        errors.append(f"{i}: 締切が不明なのに review_needed が false です")
    if it.get("source_grade") == "third_party" and not it.get("review_needed"):
        errors.append(f"{i}: 第三者の出典なのに review_needed が false です")
    pid = it.get("product_id")
    if pid and pid not in product_ids:
        errors.append(f"{i}: product_id '{pid}' が products.json にありません")
    elif not pid:
        warnings.append(f"{i}: product_id が未設定です(商品マスターに紐づいていません)")
    band[classify(it)] += 1

for s in shops:
    if s.get("chain_id") and s["chain_id"] not in chain_ids:
        errors.append(f"shops.yaml {s['id']}: chain_id '{s['chain_id']}' が chains.yaml にありません")

# --- 商品マスター(商品名と画像の紐づけ) ---
pseen, pnames = set(), {}
for p in products:
    pi = p.get("id", "(idなし)")
    if pi in pseen:
        errors.append(f"products {pi}: idが重複しています")
    pseen.add(pi)
    if not p.get("name"):
        errors.append(f"products {pi}: 商品名がありません")
    for k in [p.get("name")] + list(p.get("aliases", [])):
        key = products_lib.norm(k)
        if key in pnames and pnames[key] != pi:
            errors.append(f"products {pi}: 名前『{k}』が {pnames[key]} と重複しています(表記ゆれの二重登録)")
        pnames[key] = pi
    for e in products_lib.check_image(p.get("img_url"), p.get("img_source")):
        errors.append(f"products {pi}: {e}")
    if p.get("img_url") and not p.get("img_checked_at"):
        errors.append(f"products {pi}: 画像の出典を確認した日(img_checked_at)がありません")

# --- ゴールデンセットの形式 ---
cases = golden.get("cases", [])
if not cases:
    errors.append("tests/golden: 正解データが空です")
for c in cases:
    if "expected" not in c or "input_text" not in c:
        errors.append(f"golden {c.get('id')}: input_text か expected がありません")
    if not c.get("synthetic"):
        errors.append(f"golden {c.get('id')}: 架空データ(synthetic=true)ではありません")

# --- 広告(アフィリエイト)の規則 ---
aff = json.loads((ROOT / "data/affiliate.json").read_text(encoding="utf-8"))
ac = ops["affiliate"]
if aff.get("enabled") != ac["enabled"]:
    errors.append("affiliate: data/affiliate.json と config/operations.yaml の enabled が一致しません")
programs = {p["id"]: p for p in aff.get("programs", [])}
active_ads = [x for x in aff.get("items", []) if x.get("status") == "active"]
if not aff.get("enabled") and active_ads:
    errors.append("affiliate: 無効(enabled=false)なのに掲載中(active)の広告があります")
if len(active_ads) > ac["max_items"]:
    errors.append(f"affiliate: 掲載中の広告が上限({ac['max_items']})を超えています")
for x in aff.get("items", []):
    i = x.get("id", "(idなし)")
    cat = x.get("category")
    if cat in ac["banned_categories"]:
        errors.append(f"{i}: 禁止カテゴリ({cat})です")
    elif cat not in ac["allowed_categories"]:
        errors.append(f"{i}: 許可されていないカテゴリ({cat})です")
    if x.get("placement") != ac["placement"]:
        errors.append(f"{i}: 掲載位置が許可されていません({x.get('placement')})")
    if x.get("pr_label") is not True:
        errors.append(f"{i}: PR表示がありません")
    if x.get("is_lottery_target") is True and x.get("status") == "active":
        errors.append(f"{i}: 抽選対象商品への広告は禁止です")
    if not str(x.get("url", "")).startswith("https://"):
        errors.append(f"{i}: URLはhttpsで始まる必要があります")
    if x.get("status") == "active":
        pr = programs.get(x.get("program_id"))
        if not pr:
            errors.append(f"{i}: 提携プログラムが登録されていません")
        elif not (pr.get("approved") and pr.get("terms_checked")):
            errors.append(f"{i}: 提携の承認と規約確認が済んでいません")
print(f"広告: 有効={aff.get('enabled')} / 掲載中={len(active_ads)}件 / 下書き={len(aff.get('items', [])) - len(active_ads)}件")

if errors:
    print("検証に失敗しました:")
    for m in errors:
        print(" -", m)
    sys.exit(1)
for w in warnings:
    print("注意:", w)
print(f"検証OK: 商品{len(products)}件 / 抽選{len(items)}件 / 店舗{len(shops)}件 / チェーン{len(chains)}件 / 正解データ{len(cases)}件")
print(f"振り分け(現状): 自動公開 {band['publish']} / 確認待ち {band['queue']} / 破棄 {band['discard']}")
print(f"閾値: 自動公開 {a} 以上 / 確認待ち {q} 以上")
