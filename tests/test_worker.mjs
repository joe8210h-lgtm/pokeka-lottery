// Worker の判定・API のテスト(通信なし)。実行: node tests/test_worker.mjs
import assert from "node:assert";
import { computeEvents, validEndpoint } from "../src/events.js";
import worker, { tick, sendTick } from "../src/worker.js";

const HR = 3600e3, NOW = Date.parse("2026-11-03T12:00:00+09:00");
const it = (id, o = {}) => ({ id, status: "open", entry_end: "2026-11-09T00:00:00+09:00", ...o });

// 1. 初回は記録だけで、合図は出さない
let r = computeEvents([it("a"), it("b")], null, NOW);
assert.deepStrictEqual(r.events, []); assert.deepStrictEqual(r.state.seen, ["a", "b"]);
// 2. 新しい抽選で合図。2回目は出ない
r = computeEvents([it("a"), it("b"), it("c")], r.state, NOW);
assert.deepStrictEqual(r.events, [{ kind: "new", id: "c" }]);
assert.deepStrictEqual(computeEvents([it("a"), it("b"), it("c")], r.state, NOW).events, []);
// 3. 締切3時間前・当選発表・購入期限の前日は、1回だけ
const s0 = { seen: ["x"], fired: [] };
const items = [it("x", { entry_end: new Date(NOW + 2 * HR).toISOString(), result_date: new Date(NOW - HR).toISOString(), purchase_end: new Date(NOW + 20 * HR).toISOString() })];
r = computeEvents(items, s0, NOW);
assert.deepStrictEqual(r.events.map((e) => e.kind).sort(), ["buy", "deadline", "result"]);
assert.deepStrictEqual(computeEvents(items, r.state, NOW + 1000).events, []);
// 4. closed になった抽選の記録は掃除される
assert.ok(!computeEvents([], r.state, NOW).state.fired.length);

// 5. 宛先の検証: 許可した送信先だけ
assert.ok(validEndpoint("https://fcm.googleapis.com/fcm/send/abc"));
assert.ok(validEndpoint("https://updates.push.services.mozilla.com/wpush/v2/abc"));
assert.ok(validEndpoint("https://web.push.apple.com/abc"));
assert.ok(!validEndpoint("https://evil.example.com/x") && !validEndpoint("http://fcm.googleapis.com/x") && !validEndpoint("https://fcm.googleapis.com.evil.com/x") && !validEndpoint("https://u:p@fcm.googleapis.com/x") && !validEndpoint(null));

// 偽のKV・ASSETS
const store = new Map();
const SUBS = { async get(k, t) { const v = store.get(k); return v == null ? null : t === "json" ? JSON.parse(v) : v; }, async put(k, v) { store.set(k, v); }, async delete(k) { store.delete(k); },
  async list({ prefix }) { return { keys: [...store.keys()].filter((k) => k.startsWith(prefix)).map((name) => ({ name })), list_complete: true }; } };
let data = [it("a")];
const env = { SUBS, ASSETS: { fetch: async (u) => (typeof u === "string" && u.endsWith("/data/lotteries.json") ? new Response(JSON.stringify(data)) : new Response("page")) } };
const call = (path, body, method = "POST") => worker.fetch(new Request("https://x.test" + path, { method, body: body ? JSON.stringify(body) : undefined }), env).then(async (res) => [res.status, await res.json().catch(() => null)]);

// 6. API: 鍵の取得・登録・重複登録・解除・不正な宛先
let [st, j] = await call("/api/vapid", null, "GET");
assert.strictEqual(st, 200); assert.ok(j.publicKey.length > 80);
assert.strictEqual((await call("/api/vapid", null, "GET"))[1].publicKey, j.publicKey); // 同じ鍵を返す
const EP = "https://fcm.googleapis.com/fcm/send/abc";
assert.strictEqual((await call("/api/subscribe", { endpoint: EP }))[0], 200);
assert.strictEqual((await call("/api/subscribe", { endpoint: EP }))[0], 200);
assert.strictEqual((await call("/api/stats", null, "GET"))[1].subscribers, 1);
assert.strictEqual((await call("/api/subscribe", { endpoint: "https://evil.example.com/x" }))[0], 400);
assert.strictEqual((await call("/api/subscribe", "not json"))[0], 400);
assert.strictEqual((await call("/api/event", { type: "open" }))[0], 200);

// 7. 定期実行: 初回は送らない → 新着で送る(中身なし・VAPID署名つき) → 410 の宛先は削除
const sent = [];
const fakeFetch = async (u, o) => { sent.push([u, o]); return new Response(null, { status: sent.length > 1 ? 410 : 201 }); };
assert.deepStrictEqual(await tick(env, NOW, fakeFetch), { events: 0 }); assert.strictEqual(sent.length, 0);
data = [it("a"), it("b")];
r = await tick(env, NOW, fakeFetch);
assert.strictEqual(r.events, 1); assert.strictEqual(r.sent, 1); assert.strictEqual(sent.length, 1);
assert.ok(sent[0][1].headers.Authorization.startsWith("vapid t=") && sent[0][1].headers.Authorization.includes(", k="));
assert.strictEqual(sent[0][1].method, "POST"); assert.strictEqual(sent[0][1].body, undefined); // 本文なし
data = [it("a"), it("b"), it("c")];
r = await tick(env, NOW, fakeFetch);
assert.strictEqual(r.gone, 1);
assert.strictEqual((await call("/api/stats", null, "GET"))[1].today.gone, 1);
// 8. 画面は ASSETS に渡る
assert.strictEqual(await (await worker.fetch(new Request("https://x.test/index.html"), env)).text(), "page");
console.log("OK");
