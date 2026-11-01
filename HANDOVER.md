# ポケカ抽選・予約情報サイト 引き継ぎ資料(最新版)

更新日: 2026-11-01
読む順番: docs/HANDOFF.md → この資料 → docs/DECISIONS.md(決定の全記録) → docs/status.json(進捗) → CLAUDE.md(AI向けの指示書)
注意: この資料は「要約」です。1つにまとめた引き継ぎ指示書は docs/HANDOFF.md です。

## 1. 目的と方針
- 全国の店舗のポケモンカード抽選・予約情報を集め、見やすく無料で公開する。利用者が店舗を探し回らず、告知を見逃さないこと。
- 差別化: 応募条件の判定(「自分が応募できるか」)、支払い制限・1店舗のみ・証跡の警告、出典のランク表示、当選・落選の自前データ(今後)。
- 方針の要点: 無料で運用、競合の本文と当選率は取らない、自動応募は作らない、広告は順位に影響させない。決定の全文は DECISIONS.md。

## 2. 現在の状態(2026-11-01)
- 公開: https://pokeka-lottery.jojojo8210.workers.dev/ (Cloudflare。`.assetsignore` で .git などを非公開。/.git/config は表示されないことを確認済み)
- 検索対策: `index.html` に noindex を設定中。本番データに切り替える前に解除する。
- X収集: 1日2回(D22)。対象は50店舗に限る(D05)。
- 自動検証: GitHub Actions(validate-data)。段階1〜4の時点で緑を確認済み。以降の変更は、アップロード後に緑を確認すること(未確認)。
- データ: lotteries.json はサンプル4件のみ。締切はすべて過ぎている(本番前に差し替えるか削除する)。
- 段階A(無料の試験運用): knowledge/ 6ファイル、config/operations.yaml、tests/golden/golden.json(架空の3件)、振り分けの集計を作成済み。API呼び出しはなし。
- 段階A2(アフィリエイト): 枠と規則のみ。提携の承認前のため非表示(enabled=false)。

## 3. 反映状況の確認が必要なファイル
以下は作成済みだが、GitHubへ反映したかは未確認。Actionsで緑になるか確認すること。
- CLAUDE.md(2番、15〜17番、ルール追加分)
- data/chains.yaml(hint版)、data/schema.json(v2の summary・consistency 追加分)
- data/leads.schema.json(v2)、data/leads.json(空)、data/affiliate.json
- config/operations.yaml、tests/golden/golden.json、knowledge/ の6ファイル
- scripts/validate.py(振り分けと広告の検証を追加した版)、.github/workflows/validate.yml(config と tests を監視対象に追加)
- .assetsignore(knowledge、config、tests、docs、.claude を追加した版)
- index.html(広告枠、noindex、「応募完了」の文言)、docs/ の2ファイル

## 4. 次の作業(優先順)
1. 上の反映状況を確認する(Actionsの緑、サイトの表示)。
3. 情報源を確定する: 公式のお知らせページを3〜5件。URLを貼ってもらい、取得できるか確認する。
4. 本番の店舗リスト50件(Xアカウントはあなたが調べて入力)。
5. 自動収集の最小版(Scout、Extractor、Verifier)。APIキーはGitHub Secretsに保存する。
6. 予算の金額を決める(現在は0円)。
7. 提携プログラムへの申込みと規約確認(Amazonアソシエイト、楽天アフィリエイトなど)。
8. プライバシーポリシーと広告表記のページを用意する。
9. サンプルデータを本番データに差し替え、noindex を解除する。独自ドメインは未取得。

## 5. 運用ルール(要約。詳細は CLAUDE.md)
- 情報源は店舗の一次情報とユーザー報告のみ。他サイトは「リード」として、項目だけを取る(本文と当選率は取らない)。
- 公開する説明文は、照合済みの項目から自前で生成する。
- 自動公開は、照合が match かつ信頼度0.9以上のみ。0.7以上0.9未満は確認待ち。0.7未満は破棄。
- 抽選対象の商品には広告を貼らない。広告は一覧の下だけ、PR表記つき。
- 憲法、人格、戦略、禁止事項はエージェントが書き換えない。変更は人が承認する。

## 6. エージェント構成(計画)
運用役: Scout(収集)、Extractor(構造化)、Verifier(検証)、Summarizer(説明文)、Publisher(公開)、Notifier(通知)、Watchdog(監視・失敗の記録)、Analyst(改善案の提案のみ)。
権限表は CLAUDE.md と knowledge/ を参照。段階の進め方: A(無料・手動の試験)→ B(API・GitHub Actions)→ C(有料のClaude Codeでサブエージェント)。

## 7. 費用と制約
- 現在: 無料(GitHub、Cloudflare、Web Push の無料枠)。API利用は0円の設定。
- 従量: Claude API(小規模で月数百〜千円台の見込み)、X API(取得1件あたり約0.005ドル。商用利用は規約の確認が必要)。
- 有料化: Claude Codeの有料プラン(料金は公式で確認)。
- 制約: 外部サイトは、メッセージに貼られたURLのみ開ける。ログインが要る応募ページは自動収集できない可能性が高い。cardchusenの規約は未確認。

## 8. 引き継ぎの方法(決定事項 D23)
- 会話の全文は引き継がない(膨大なため)。引き継ぎは、指示書 `docs/HANDOFF.md` で行う。設計図、Gitの状態、運用方針、今後の予定、未決事項をまとめてある。
- 新しいアカウントでは、HANDOFF.md を最初のメッセージとして貼るか、リポジトリの docs/ から読ませる。
- 一語一句の再現は保証しない。迷ったら、CLAUDE.md、DECISIONS.md、ユーザー本人に確認する。
- 秘密情報(APIキー、パスワード、ログイン情報)は、どの資料にも書かない。
