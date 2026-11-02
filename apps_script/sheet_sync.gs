/**
 * スプレッドシート → GitHub Issue 連携
 * ・1行追加(店舗名あり・状態が空) → X取込のIssueを作る(ラベル x-intake, review-needed)
 * ・J列(確認済み)にチェック → そのIssueを「確認済み」にし、ラベル approved を付ける
 * 公開の最終判断は、GitHub上のPRを人がマージしたときだけ。
 * 列: A店舗名 B投稿のURL C商品名 D受付方法 E受付開始 F受付終了 G発表日 H必要なもの I支払い制限 J確認 K状態 L商品画像のURL M画像の出典URL
 * (2026-11-02 L・M列を追加。商品名と画像の紐づけ。D32)
 * 注意: これはAppsScriptの控え。末尾の installTrigger は、貼り付けが途中で切れていたため、定型の終わり方で補っている。
 */
const REPO = 'joe8210h-lgtm/pokeka-lottery';
const COL = { store: 0, url: 1, product: 2, channel: 3, start: 4, end: 5, result: 6, req: 7, pay: 8, checked: 9, status: 10, img: 11, imgsrc: 12 };

function fmt(v) {
  if (v instanceof Date) return Utilities.formatDate(v, 'Asia/Tokyo', 'yyyy-MM-dd HH:mm');
  if (v === '' || v === null || v === undefined) return '';
  return String(v).trim();
}

function ghFetch(method, path, payload) {
  const token = PropertiesService.getScriptProperties().getProperty('GITHUB_TOKEN');
  if (!token) throw new Error('スクリプトプロパティに GITHUB_TOKEN がありません');
  const res = UrlFetchApp.fetch('https://api.github.com/repos/' + REPO + path, {
    method: method,
    headers: { Authorization: 'Bearer ' + token, Accept: 'application/vnd.github+json' },
    contentType: 'application/json',
    payload: payload ? JSON.stringify(payload) : undefined,
    muteHttpExceptions: true,
  });
  const code = res.getResponseCode();
  if (code >= 300) throw new Error('GitHub ' + code + ': ' + res.getContentText().slice(0, 200));
  return JSON.parse(res.getContentText());
}

// 行の内容を、Issueフォームと同じ見出しの本文にする(読み取りスクリプトが読める形)
function buildBody(r, checked) {
  const v = (x) => (x ? x : '_No response_');
  const rows = [
    ['店舗名', v(r[COL.store])],
    ['投稿のURL(店舗の公式アカウントのもの)', v(r[COL.url])],
    ['商品名', v(r[COL.product])],
    ['商品画像のURL', v(r[COL.img])],
    ['画像の出典URL', v(r[COL.imgsrc])],
    ['受付方法', v(r[COL.channel])],
    ['受付開始(日本時間)', v(r[COL.start])],
    ['受付終了(日本時間)', v(r[COL.end])],
    ['当選発表日', v(r[COL.result])],
    ['必要なもの(短く)', v(r[COL.req])],
    ['支払いの制限', v(r[COL.pay])],
    ['確認状況', (checked ? '- [x] ' : '- [ ] ') + '店舗の公式サイトまたは店頭で、この内容を確認した'],
  ];
  return rows.map(function (x) { return '### ' + x[0] + '\n\n' + x[1]; }).join('\n\n');
}

function syncIntake() {
  const sheet = SpreadsheetApp.getActiveSpreadsheet().getSheets()[0];
  const values = sheet.getDataRange().getValues();
  for (let i = 1; i < values.length; i++) {
    const row = values[i];
    const rowNo = i + 1;
    const store = fmt(row[COL.store]);
    if (!store) continue;
    const status = fmt(row[COL.status]);
    try {
      if (!status) {
        // 新しい行: Issueを作る
        const product = fmt(row[COL.product]);
        const issue = ghFetch('post', '/issues', {
          title: '[X取込] ' + store + ' / ' + (product || '商品名未入力'),
          body: buildBody(row.map(fmt), false),
          labels: ['x-intake', 'review-needed'],
        });
        sheet.getRange(rowNo, COL.status + 1).setValue('作成済み #' + issue.number);
      } else if (status.indexOf('作成済み') === 0 && row[COL.checked] === true) {
        // 確認済みにチェックされた: Issueを確認済みにして、承認ラベルを付ける
        const num = status.match(/#(\d+)/)[1];
        ghFetch('patch', '/issues/' + num, { body: buildBody(row.map(fmt), true) });
        ghFetch('post', '/issues/' + num + '/labels', { labels: ['approved'] });
        sheet.getRange(rowNo, COL.status + 1).setValue('承認済み #' + num);
      }
    } catch (e) {
      sheet.getRange(rowNo, COL.status + 1).setValue('エラー: ' + e.message);
    }
  }
}

// 最初に1回だけ実行する: 10分ごとに syncIntake を自動で動かす
function installTrigger() {
  ScriptApp.getProjectTriggers().forEach(function (t) {
    if (t.getHandlerFunction() === 'syncIntake') ScriptApp.deleteTrigger(t);
  });
  ScriptApp.newTrigger('syncIntake').timeBased().everyMinutes(10).create();
}
