# 引き継ぎ指示書(ポケカ抽選・予約情報サイト)

作成日: 2026-11-01 / これ1つで、設計・Gitの状態・運用方針・今後の予定を引き継げるようにまとめた指示書です。
使い方: 新しいアカウントのClaude(Claude Code)に、このファイルを最初のメッセージとして貼るか、リポジトリの docs/ に置いて「これを読んで、現状と次の作業を説明して」と頼む。
注意: 会話の全文は引き継がない。これは要約であり、一語一句の再現は保証しない。迷ったら、リポジトリのファイル(CLAUDE.md、docs/DECISIONS.md)と、ユーザー本人に確認すること。

---

## 0. あなた(引き継ぐAI)への指示

1. まず、この資料と、リポジトリの `CLAUDE.md`、`docs/DECISIONS.md`、`docs/status.json` を読む。
2. 「現状」「反映が未確認のもの」「次の作業」を、ユーザーに短く報告する。
3. 作業は、**1つの手順ずつ**進める。各手順のあとに、ユーザーの「できた」を待つ。
4. 回答は、**結論を先に**、そのあとに理由と具体例、改善案を書く。抽象論は避け、具体例で説明する。ユーザーの提案以外の提案も出す。
5. ユーザーはエンジニアではなく、主にスマホ(Claudeアプリ)とGitHubのWeb画面で作業している。専門用語は避け、画面の操作を1つずつ、番号つきで案内する。日本語で答える。
6. 決まっていない事項や、確認できていない事実を、推測で埋めない。分からないことは「未確認」と書く。
7. APIキー、パスワード、アカウント識別子は、資料にもチャットにも書かない。

## 1. プロジェクトの目的

- 全国の店舗のポケモンカードの抽選・予約情報を集め、見やすく**無料で**公開するサイト。
- 利用者が各店舗を探し回らず、新しい告知を見逃さないこと。
- 競合に勝つ軸: ①応募条件の判定(「自分が応募できるか」を自動で示す)、②支払い制限・「1店舗のみ」・控えの保管などの警告、③出典のランク表示、④当選・落選の自前データ(今後)、⑤告知から掲載までの速さ。
- 競合: cardchusen(受付中約280件、LINE通知あり、評価67点)、ポケカ抽選図鑑(受付中71件、店舗654)、トレカの地図(大手13〜14チェーンの記事)。共通の弱点は、条件で絞れない、当選データが薄い、鮮度の保証がない。

## 2. 決定事項(要約。全文は docs/DECISIONS.md の D01〜D22)

- 無料で始める。公式LINEは後回し。通知はWeb Pushを先に。Claude Codeの有料版は後でアップグレードする。
- X収集は、頻繁にXで告知する店舗、またはXのみで告知する店舗、計50件に限る。**頻度は1日2回**(D22)。
- 競合サイトの本文と当選率は取らない・転載しない。他サイトは「リード」(新しく抽選を始めた店舗の発見)として、項目に分けた事実だけを取る。リードの要件は「ヒント」で、店舗の一次情報で確認できるまで公開しない。
- 公開する説明文は、照合済みの項目から自前で生成する。他サイトの文章の言い換えは使わない。
- 店舗フォームへの自動応募は作らない。
- 応募条件は抽選ごとに変わる。その抽選の告知の値を、チェーンの既定値より優先する。
- ボタン名は「応募完了」。応募時刻は端末のブラウザ内にだけ保存する。
- 自動公開は、信頼度0.9以上かつ照合が match のときだけ。0.7以上0.9未満は確認待ち。0.7未満は破棄。最初は shadow_mode(公開せず記録のみ)。API予算は0円。
- カードゲーム関連の周辺商品のみ、アフィリエイトを行う。抽選対象の商品、オリパ、ガチャ、転売には貼らない。広告は一覧の下だけ、PR表記つき。順位や判定に影響させない。提携の承認と規約確認が済むまで非表示。
- エージェントは、憲法(CLAUDE.md)、人格(profile)、戦略(strategy)、禁止事項(ng-rules)を書き換えない。変更は人が承認する。

## 3. システムの設計図

### 3-1. 流れ
Scout(収集)→ Extractor(項目に分ける)→ Verifier(照合・検査)→ Summarizer(説明文の生成)→ Publisher(公開)→ Notifier(通知)。Watchdog が失敗を監視して learn.md に記録し、Analyst が改善案をPRで提案する。

### 3-2. エージェントの権限
| 役 | 読む | 書く | 書けない |
|---|---|---|---|
| Scout | CLAUDE, ng-rules | 取得した生データ(一時) | 公開データ |
| Extractor | CLAUDE, domain, references | 抽選データの下書き | 憲法・禁止事項 |
| Verifier | CLAUDE, domain, chains, ng-rules | 照合結果、確認待ちの印 | 公開データ |
| Summarizer | profile, ng-rules, schema | 説明文(照合済みの項目のみが入力) | 他サイトの文章 |
| Publisher | CLAUDE, strategy | 検証を通ったものの公開 | 検証の判定 |
| Notifier | strategy, profile | 通知の送信 | 抽選データ |
| Watchdog | learn, ng-rules | learn への失敗の記録 | 憲法・人格・戦略 |
| Analyst | learn, references | 改善案のPRのみ | 憲法・人格・戦略・禁止事項 |

### 3-3. 運用エージェントと開発エージェントは別物
- 運用用: 本番で毎日動くもの。GitHub Actions + API(従量課金)で動かす。
- 開発用: Claude Codeのサブエージェント(`.claude/agents/`)。エージェントチーム機能は、実験的で既定は無効、トークン消費が大きい。使う場面は、「抽出と検証の反論」と「複数チェーンの規約調査の並列化」だけに絞る。有料化後に導入。

### 3-4. データの形式(data/schema.json v2)の要点
- 識別: id、shop_id、shop_name、chain_id、route_id、store_type(chain / local_shop / maker_campaign)。
- 内容: product、method(online / store / unknown)、entry_channel(web_form / x_repost / app / in_store / invitation / receipt_upload / unknown)、window_type(fixed / rolling)。
- 日時(日本時間 +09:00 のISO形式): entry_start、entry_end、result_date、purchase_start、purchase_end。
- 受取: delivery(store / mail / choice / unknown)、shrink(kept / removed / unknown)、price_yen、limit_per_person。
- 応募: entry_steps(type と label の配列)、requirements(key、label、detail の配列)、payment(restriction: none / own_card_only / unknown、required_card、timing)。
- 注意書き: proof_note(控えの保管)、penalty_note、may_close_early、exclusive_group(同じ値の抽選は1つしか応募できない)、win_rate_ref(参考値のみ)。
- 出典と品質: source_type、source_grade(official / store_notice / third_party)、source_url、first_seen_at、last_verified_at、confidence(0〜1)、review_needed、summary(自前の説明文、160字以内)、consistency(status: match / conflict / unverified、checked_at、conflict_fields)。
- マイ設定で自動判定する requirements.key: mynumber_card、aeon_card、biccamera_card、yodobashi_member。それ以外(member、app、id_check、receipt、purchase_history など)は「要確認」と表示する。
- リード(data/leads.schema.json v2): 店舗名、チェーン、地域、店舗のXアカウント、商品、日時、受付方法、requirements_hint(label は40字以内)、payment_restriction、primary_url(店舗自身の元の告知URL)、status(new / matched / collected / dismissed)、note(80字以内)。source_grade は常に third_party。
- 公開の振り分け(scripts/validate.py): 確認待ちの印があるか照合が match でなければ、信頼度0.7以上で確認待ち、未満で破棄。match かつ確認待ちの印なしで0.9以上なら自動公開。

## 4. ポケカ抽選の専門知識(確認できた事実)

- **イオンスタイルオンライン(規約の画像で確認済み):** 決済は、注文者と同一名義の「イオンカード」のみ。デビット・プリペイドは不可。1商品につき1人(1世帯・同一住所)1回。複数アカウント・メール・電話番号での重複応募は全て無効。当選はメールで通知し、当落の問い合わせは不可。当選の権利は譲渡不可。注文後のキャンセル・返品・交換は不可。届け先の不備は事前通告なくキャンセル。日本国内のみ。
- **ビックカメラ:** 条件は店舗・抽選ごとに変わる。池袋本店の7月の抽選(店頭ポスターで確認済み): 指定レジで受付。対象はポイントカード、Suica等の提携カード、公式アプリ(コジマ・ソフマップのカードは対象外)。カードは告知前の基準日までに発行・情報登録済みであること。指定期間(約2年間)の購入履歴が必要。本人名義のマイナンバーカードが必要。複数店舗で同時実施されても応募は1店舗のみ。レシートが控えと当選引換券を兼ね、再発行不可。発表は店頭掲示と店舗の公式X。購入期間は発表の翌日から3日間。シュリンクと外箱は回収。受付を途中で打ち切る場合あり。10月の4店舗の抽選は、第三者の投稿のみ(未検証): Suicaカード会員限定、仮カード不可、受付開始時間が店舗で違う。
- **ヨドバシ(ユーザー提供の画像。公式で要確認):** 会員(入会無料)と、過去2年の購入履歴(ヨドバシ.com、またはポイント共通化済みの店舗購入)。基準日は抽選ごとに異なる。受付は11:00〜翌10:59、発表は翌日18:00、注文期限は翌々日23:59というパターンが、2023〜2025年の複数の抽選で続いている。応募は専用サイトで、ログインが必要(自動収集は難しい)。
- **その他のチェーン:** 競合サイトの記載を要約した「ヒント」のみ(data/chains.yaml の hint。すべて未検証)。公式で確認するまで、画面の条件には使わない。
- **競合の傾向:** ポケカ抽選図鑑では、受付中の約3分の2(48/71件)がXのフォロー&リポスト系。

## 5. Git(GitHub)と公開の現在の状態

- リポジトリ: `jojojo8210-commits/pokeka-lottery`(Public)。公開サイト: https://pokeka-lottery.jojojo8210.workers.dev/ (Cloudflare Workers の静的アセットで配信。mainに保存すると自動で再公開)。
- 構成: index.html、CLAUDE.md、.assetsignore、data/(schema.json、lotteries.json、chains.yaml、shops.yaml、leads.schema.json、leads.json、affiliate.json)、config/operations.yaml、knowledge/(profile、strategy、domain、references、ng-rules、learn)、tests/golden/golden.json、scripts/validate.py、.github/workflows/validate.yml、docs/。
- **確認済み:** リポジトリ、設計ファイル(第1版)、一覧サイトの公開、Actionsの自動検証の成功(緑)、`.git` が公開されないこと(/.git/config が表示されない)。
- **作成済みだが、GitHubへの反映が未確認:** 以降に作った更新・追加分すべて(chains.yaml のヒント版、schema.json の summary と consistency、leads の2ファイル、affiliate.json、config、tests、knowledge の6ファイル、validate.py の更新版、validate.yml の更新版、.assetsignore の更新版、index.html の広告枠版、docs/ の資料)。**最初に、GitHubのファイル一覧とActionsの緑チェックで、反映状況を確認すること。**
- 現在の抽選データ(lotteries.json)は、架空のサンプル4件のみ。締切はすべて過ぎている。noindex(検索結果に出ない指定)を設定中。
- 独自ドメインは未取得。

## 6. 運用方針

- 情報源: 店舗の一次情報(公式X、公式サイト、RSS、店頭ポスター、規約)とユーザー報告。他サイトはリード(店舗の発見)のみ。
- 他サイトの自動取得は、各サイトの利用規約と robots.txt を確認してから。頻度は1日2回以内。最初は手動(ユーザーがURLを貼って、項目を抽出する)。
- 外部サイトの確認は、メッセージに貼られたURLなら開ける環境だった(別の環境では異なる場合がある)。ログインが必要な応募ページは自動収集しない。
- 日付が不明なものを「調査中」のまま放置しない。review_needed を true にして確認待ちにする。画像だけの告知は、読めない項目を null にし、推測で埋めない。
- 説明文は、断定できない項目を「未確認」と書く。「必ず当たる」「今すぐ」などの煽りは禁止。
- 変更は小さく、1つずつ。データを変えたら、自動検証が通ることを確認してから公開する。
- 失敗は learn.md に、「症状、原因、再発防止、対応したファイル」の4項目で記録する。
- 目標値: 抽出が人の確認と一致する割合95%以上、「調査中」5%未満、重複0件、告知から掲載まで30分以内、正解データの正解率95%以上。

## 7. 費用

- 現在は0円(GitHub、Cloudflare、Web Pushの無料枠)。API予算は0円の設定。
- 今後の目安: ドメイン年約2,000〜3,000円。Claude APIは小規模で月数百〜千円台。X APIは取得1件あたり約0.005ドル(50店舗でキーワードを絞って月千円前後の見込み)で、**商用利用は規約の確認が必要**。Claude Codeの有料プランは、料金を公式で確認する。

## 8. 過去に起きた問題と対策(learn)

- `.gitignore` をアップロードすると、名前が「download」に変わった → 隠しファイル(先頭がドット)は、GitHubの「Create new file」で名前を入力して作る。
- Cloudflareの新しい方式では、`.git` フォルダまで公開用にアップロードされた → `.assetsignore` で除外。公開後に `/.git/config` を開いて、表示されないことを確認する。
- サンプルの `shop_id` が `shops.yaml` に無く、条件が二重に表示された → 検証スクリプトで参照を自動チェックし、`conditions` を廃止して `requirements` に一本化した。
- ファイルを上書きするときは、名前が「(1)」などで変わっていないか確認する。
- 端末の出力を日本語の途中で切ると、文字化けする(出力の途中切り取りに注意)。

## 9. 今後の予定(優先順)

1. 反映の確認: GitHubのファイル一覧、Actionsの緑、サイトの表示。
2. サンプルデータの整理(本番前に差し替えか削除)。
3. 情報源の確定: 公式のお知らせページ3〜5件(ユーザーがURLを貼る)。取得できるか、ログインが要るか、画像のみかを判定する。
4. 本番の店舗リスト50件(Xアカウントは、ユーザーが調べて入力)。
5. 収集の最小版(Scout、Extractor、Verifier)。APIキーはGitHub Secretsに保存する。予算の金額をユーザーと決める。
6. リード検出(最初は手動)と、利用規約・robots.txtの確認。
7. 提携プログラム(Amazonアソシエイト、楽天アフィリエイト等)への申込みと規約確認。プライバシーポリシーと広告表記のページを用意する。
8. 通知(Web Push)、当選・落選の報告、穴場スコア。
9. 独自ドメインの取得、noindexの解除、収益化。
10. Claude Codeへの移行、サブエージェントの導入。正解データを20〜30件に増やし、影の運用(1週間)を経て本番へ。

## 10. 未決事項

- 予算の金額(現在0円)。
- 情報源の確定(公式のお知らせページのURL)。
- X APIの商用利用の可否と費用。
- cardchusenなどの規約とrobots.txtの確認(cardchusenの規約は未確認)。
- 提携プログラムの選定。
- 反映が未確認のファイルの状態。
