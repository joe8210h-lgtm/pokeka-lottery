# サンプルから本番への項目対応表(手順1)

作成: 2026-11-03。サンプル(3d-ui-sample.html、公開版v63)の項目を、`data/schema.json`・`products.json`・`shops.yaml`・`chains.yaml` に対応させる。
コードは変えていない。手順2(見た目の移植)で使う。

## 1. そのまま対応できる項目

| サンプルの項目 | 意味 | 本番の項目 | 備考 |
|---|---|---|---|
| id | 抽選の識別子 | lotteries.id | |
| m | online / store | method | schemaには `unknown` もある。表示は「方式未確認」を追加 |
| s | 店舗名 | shop_name | チェーン名は chain_id → chains.yaml の name |
| p | 商品名 | product(表示名は products.json の name を優先) | product_id が無い抽選は product を使う |
| open | 受付開始(日時) | entry_start | |
| due | 受付終了(日時) | entry_end | rolling(window_type)は終了なし。表示を決める必要がある |
| wnAt | 当選発表(日時) | result_date | |
| wn | 当選発表(表示文) | result_date と announce.channel から生成 | 文は手順2で関数にする |
| bp | 購入期間(表示文) | purchase_start / purchase_end から生成 | |
| bpEnd | 購入期限(日時) | purchase_end | |
| pr | 価格(表示文) | price_yen から生成 | 税込・BOX等の単位は products.json に持たせる(下の不足1) |
| src | 出典 | source_type / source_url / source_grade | 画面の表示は source_grade の3種類(official / store_notice / third_party) |
| url | 応募先リンク | apply_url | 無いとき「応募する！」は出さず、出典へのリンクにする(CLAUDE.md 3番) |
| img | 商品画像 | products.json の img_file(`assets/products/*.webp`) | 画像の置き場所は決まっている。埋め込みは外す |

## 2. 計算で作る項目(データには持たない)

| サンプルの項目 | 作り方 |
|---|---|
| h(残り時間) | 実行時の時刻と entry_end の差。サンプルは基準時刻を固定(NOW)しているので、本番は現在時刻に変える |
| pre(受付前) | status が upcoming、または現在時刻が entry_start より前 |
| ot, rc(表示用の日付文) | entry_start / entry_end から生成(日本時間、曜日つき) |
| 残り時間の色(赤/黄/青/水色/灰) | h と pre から決める(card-ui.md の既存ルール) |
| st(応募可/要確認/終了) | 下の不足3で決める |
| _rg(地域) | shops.yaml の prefecture から地域グループに変換(下の不足2) |

## 3. 対応が必要な項目(不足)

1. **商品の単位情報:** サンプルは「/BOX」「30P入り・200円/P」「1人1BOXまで」を文字で持つ。schemaには `limit_per_person` と `price_yen` しかない。
   - 案: products.json に `unit`(BOX / セット / パック)と `packs`(入数)を追加し、1パックあたりの価格は実行時に計算する。
   - 種類(k: pack / box / set)も products.json に持たせる。
2. **地域:** サンプルは店名の文字列で地域を判定している(RMAP)。本番は店名では判定しない。
   - shops.yaml の `prefecture` と `area` から、9つの地域グループ(一都3県、北海道、東北、北関東、中部、関西、中国・四国、九州・沖縄、全国・オンライン)への対応表を、JSで1つ持つ。
   - shop_id が shops.yaml に無い抽選は「地域未確認」にする(現在のサンプルと同じ扱い)。
3. **判定(応募可/要確認/終了):** サンプルは固定で `warn`(要確認)にしている。本番は次のように決める案。
   - 終了: 受付終了を過ぎている。
   - 要確認: `review_needed` が true、`confidence` が 0.8 未満、`source_grade` が third_party、`consistency.status` が conflict または unverified、受付期間が不明のいずれか。
   - 応募可: 上のどれでもない。
   - 「応募可」は、CLAUDE.md の「確認済みとして公開しない」と矛盾しない条件に限る。迷ったら要確認にする。
4. **条件アイコンの対応:** サンプルのアイコンの種類と、schema の `requirements.key` が一致しない。

   | サンプルのアイコン | schema の key(候補) |
   |---|---|
   | member(会員登録) | member / yodobashi_member / biccamera_card / aeon_card |
   | app(アプリ) | app |
   | receipt(レシート) | receipt |
   | history(購入履歴) | purchase_history |
   | id(本人確認) | id_check / mynumber_card |
   | pay(支払い) | payment.restriction が own_card_only のとき |
   | livepocket | entry_channel が web_form で livepocket のとき(key の追加が必要) |

   - 対応表はJSに持つ。未知の key は、アイコンなしの文字で表示する。
5. **マイ設定の自動判定:** サンプルは条件の文章を正規表現で判定している。本番は `requirements.key` が mynumber_card / aeon_card / biccamera_card / yodobashi_member のときだけ自動判定し、それ以外は「要確認」にする(CLAUDE.md 13番)。サンプルの正規表現は使わない。
6. **サンプルの表示だけの項目:** 「(サンプル)」の表示、固定の基準時刻、デモ用の操作(発表時刻を過ぎたことにする)は、本番では外す。

## 4. 本番に移さないもの(この段階では)
- 履歴、あとで応募、フォロー、報告、カレンダー、統計、購入パス。これらは手順3で、機能ごとに別のPRにする。
- 埋め込みの抽選データ29件と、埋め込みの画像。

## 5. 手順2で最初に決めること
- 実データは現在 `data/lotteries.json` に4件(すべてサンプル)しかない。サンプルの29件は本番データに無い。
  - 手順2の確認は、サンプルの29件を `data/lotteries.json` の形式に変換した確認用ファイルで行う案。本番のデータには入れない。
  - 確認用ファイルの置き場所: `tests/fixtures/`。
