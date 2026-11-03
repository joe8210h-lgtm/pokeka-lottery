# 公開前の切り替え手順(サンプル差し替え・noindex解除)

作成: 2026-11-03。公開の判断はユーザー。ここでは手順だけを決める。

## サンプルの差し替え
1. `data/lotteries.json` の `sample-` で始まる4件を、実データ(店舗の一次情報で確認したもの)に置き換える。終了済みは closed で残す。
2. 画面の「動作確認用のサンプルです」は、id が `sample` で始まるものが1件でもあると出る。全て消えれば出なくなる。
3. 実データには `prefecture` を入れなくてよい(`data/shops.json` から補う)。商品は `data/products.json` の `product_id` で結ぶ。
4. `python scripts/validate.py` が通ることを確認する。

## noindex の解除(ユーザーの承認が必要)
- 対象: `index.html` の `<meta name="robots" content="noindex">`。`privacy.html` も同様。
- 解除の前に確認: 運営者名と連絡先を `privacy.html` に記入済み / サンプルが残っていない / 要確認の表示が出ている / 広告を入れるなら「PR」表記済み。
