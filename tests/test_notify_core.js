// 通知の判定のテスト。実行: node tests/test_notify_core.js
const assert = require('assert');
const N = require('../notify-core.js');
const J = 9 * 3600e3, H = 3600e3;
const at = (iso) => Date.parse(iso);
const NOW = at('2026-11-03T12:00:00+09:00');
const P = (o) => ({ on: true, ...o });
const mk = (id, o = {}) => ({ id, shop_name: 'ビックカメラ池袋本店', product: '拡張パック「アビスアイ」', status: 'open', review_needed: false, confidence: 0.95,
  source_grade: 'store_notice', consistency: { status: 'match' }, first_seen_at: '2026-11-03T11:00:00+09:00', entry_end: '2026-11-05T23:59:00+09:00', requirements: [], ...o });
const run = (items, extra = {}) => N.decide({ items, prefs: P(extra.prefs), my: extra.my, hist: extra.hist, follow: extra.follow, notified: extra.notified, counts: extra.counts, now: extra.now || NOW });

// 1. オフなら何もしない
assert.deepStrictEqual(N.decide({ items: [mk('a')], prefs: { on: false }, now: NOW }).show, []);

// 2. 確認済みの新着は通知、未確認はバッジだけ(精度案2)
let r = run([mk('a'), mk('b', { review_needed: true })]);
assert.strictEqual(r.show.length, 1); assert.strictEqual(r.show[0].id, 'a'); assert.strictEqual(r.badge, 1);
assert.ok(r.mark.includes('a:new') && !r.mark.includes('b:new'));

// 3. 条件に合わない抽選は通知しない(精度案1)。マイ設定が未入力なら絞らない
const need = mk('c', { requirements: [{ key: 'mynumber_card', label: 'x' }] });
assert.strictEqual(run([need], { my: { set: 1, mn: 0 } }).show.length, 0);
assert.strictEqual(run([need], { my: { set: 1, mn: 1 } }).show.length, 1);
assert.strictEqual(run([need], { my: { set: 0 } }).show.length, 1);

// 4. 通知済みは出さない(重複排除・精度案5)
assert.strictEqual(run([mk('a')], { notified: ['a:new'] }).show.length, 0);

// 5. 同時の新着は1件にまとめる(精度案4)
r = run([mk('a'), mk('b'), mk('c')]);
assert.strictEqual(r.show.length, 1); assert.ok(r.show[0].title.includes('3件')); assert.strictEqual(r.mark.length, 3);

// 6. 締切3時間前: 確認済み・未応募・終了日あり
const dl = mk('d', { entry_end: '2026-11-03T14:30:00+09:00' });
r = run([dl], { prefs: { kinds: { new: false, deadline: true, result: true, buy: true } } });
assert.strictEqual(r.show[0].kind, 'deadline'); assert.ok(r.show[0].title.includes('3時間'));
assert.strictEqual(run([mk('e', { entry_end: '2026-11-03T16:00:00+09:00' })], { prefs: { kinds: { new: false, deadline: true } } }).show.length, 0); // 4時間先は対象外
assert.strictEqual(run([{ ...dl, review_needed: true }], { prefs: { kinds: { new: false, deadline: true } } }).show.length, 0); // 未確認は時刻を通知しない
assert.strictEqual(run([dl], { prefs: { kinds: { new: false, deadline: true } }, hist: { d: { st: 'applied' } } }).show.length, 0); // 応募済みは締切通知しない

// 7. 当選発表日(応募済みのみ)・購入期限の前日(当選のみ)
const res = mk('f', { result_date: '2026-11-03T10:00:00+09:00', status: 'closed' });
assert.strictEqual(run([res], { hist: { f: { st: 'applied' } } }).show[0].kind, 'result');
assert.strictEqual(run([res]).show.length, 0);
const buy = mk('g', { purchase_end: '2026-11-04T09:00:00+09:00', status: 'closed' });
assert.strictEqual(run([buy], { hist: { g: { st: 'won' } } }).show[0].kind, 'buy');
assert.strictEqual(run([buy], { hist: { g: { st: 'lost' } } }).show.length, 0);

// 8. おやすみ時間(23〜7時)は出さず、通知済みにもしない
const night = at('2026-11-03T23:30:00+09:00');
r = run([mk('a', { first_seen_at: '2026-11-03T22:00:00+09:00' })], { now: night });
assert.strictEqual(r.show.length, 0); assert.strictEqual(r.mark.length, 0); assert.strictEqual(r.deferred, 1);
assert.strictEqual(run([mk('a')], { prefs: { quiet: false }, now: night }).show.length, 1);

// 9. 1日の上限(既定5)。自分の応募に関わる通知を新着より先に出す
const many = ['a', 'b', 'c', 'd', 'e', 'f'].map((i) => mk(i, { entry_end: '2026-11-03T13:00:00+09:00' }));
r = run(many, { prefs: { kinds: { new: false, deadline: true } }, counts: { day: '2026-11-03', n: 3 } });
assert.strictEqual(r.show.length, 2); assert.strictEqual(r.deferred, 4);
assert.strictEqual(run(many, { prefs: { kinds: { new: false, deadline: true } }, counts: { day: '2026-11-02', n: 9 } }).show.length, 5); // 日付が変われば0から

// 10. フォロー店舗だけ
assert.strictEqual(run([mk('a')], { prefs: { onlyFollow: true }, follow: ['ヨドバシ'] }).show.length, 0);
assert.strictEqual(run([mk('a')], { prefs: { onlyFollow: true }, follow: ['ビックカメラ'] }).show.length, 1);

// 11. 古い新着(48時間以上前)は、登録直後に大量に出さない
assert.strictEqual(run([mk('old', { first_seen_at: '2026-10-20T10:00:00+09:00' })]).show.length, 0);

// 12. 通知のURLは抽選のカードを開く
assert.strictEqual(run([mk('a/b')]).show[0].url, './?lottery=a%2Fb');
console.log('OK');
