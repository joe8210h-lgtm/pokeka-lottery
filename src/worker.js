// ラッフレアの通知用 Worker。静的な画面は ASSETS が返し、/api/* と定期実行(cron)だけここで処理する。
// 保存するのは通知の宛先(endpoint)だけ。名前・メール・フォロー店舗・応募履歴・条件は保存しない。
// 合図(push)は中身なし。端末の service worker が最新データを読み、端末内の設定で通知するか決める。
import { computeEvents, validEndpoint } from "./events.js";

const SITE = "https://pokeka-lottery.jojojo8210.workers.dev";
const MAX_SUBS = 5000;
const b64u = (buf) => btoa(String.fromCharCode(...new Uint8Array(buf))).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
const json = (o, s = 200) => new Response(JSON.stringify(o), { status: s, headers: { "content-type": "application/json", "cache-control": "no-store" } });
const hash = async (s) => b64u(await crypto.subtle.digest("SHA-256", new TextEncoder().encode(s)));
const day = (now = Date.now()) => new Date(now + 9 * 3600e3).toISOString().slice(0, 10);

async function vapid(env) {
  let k = await env.SUBS.get("vapid", "json");
  if (!k) { // 初回だけ鍵を作って保存する(手作業の登録は不要)
    const pair = await crypto.subtle.generateKey({ name: "ECDSA", namedCurve: "P-256" }, true, ["sign", "verify"]);
    k = { priv: await crypto.subtle.exportKey("jwk", pair.privateKey), pub: b64u(await crypto.subtle.exportKey("raw", pair.publicKey)) };
    await env.SUBS.put("vapid", JSON.stringify(k));
  }
  return k;
}

async function jwt(env, endpoint) {
  const k = await vapid(env);
  const head = b64u(new TextEncoder().encode(JSON.stringify({ typ: "JWT", alg: "ES256" })));
  const body = b64u(new TextEncoder().encode(JSON.stringify({ aud: new URL(endpoint).origin, exp: Math.floor(Date.now() / 1000) + 12 * 3600, sub: SITE })));
  const key = await crypto.subtle.importKey("jwk", k.priv, { name: "ECDSA", namedCurve: "P-256" }, false, ["sign"]);
  const sig = await crypto.subtle.sign({ name: "ECDSA", hash: "SHA-256" }, key, new TextEncoder().encode(head + "." + body));
  return `vapid t=${head}.${body}.${b64u(sig)}, k=${k.pub}`;
}

async function bump(env, field, n = 1) {
  const key = "stat:" + day(), cur = (await env.SUBS.get(key, "json")) || {};
  cur[field] = (cur[field] || 0) + n;
  await env.SUBS.put(key, JSON.stringify(cur), { expirationTtl: 60 * 86400 });
}

export async function sendTick(env, fetcher = fetch) {
  let cursor, sent = 0, gone = 0;
  do {
    const page = await env.SUBS.list({ prefix: "sub:", cursor });
    cursor = page.list_complete ? undefined : page.cursor;
    for (const { name } of page.keys) {
      const sub = await env.SUBS.get(name, "json");
      if (!sub) continue;
      try {
        const res = await fetcher(sub.endpoint, { method: "POST", headers: { Authorization: await jwt(env, sub.endpoint), TTL: "3600", Urgency: "normal", "Content-Length": "0" } });
        if (res.status === 404 || res.status === 410) { await env.SUBS.delete(name); gone++; } else if (res.ok) sent++;
      } catch { /* 次の周期でまた試す */ }
    }
  } while (cursor);
  if (sent) await bump(env, "sent", sent);
  if (gone) await bump(env, "gone", gone);
  return { sent, gone };
}

async function lotteries(env) {
  const r = await env.ASSETS.fetch("https://assets.invalid/data/lotteries.json");
  return r.ok ? r.json() : null;
}

export async function tick(env, now = Date.now(), fetcher = fetch) {
  const items = await lotteries(env);
  if (!items) return { skipped: "data" };
  const { events, state } = computeEvents(items, await env.SUBS.get("state", "json"), now);
  await env.SUBS.put("state", JSON.stringify(state));
  if (!events.length) return { events: 0 };
  return { events: events.length, ...(await sendTick(env, fetcher)) };
}

async function api(req, env, url) {
  if (url.pathname === "/api/vapid" && req.method === "GET") return json({ publicKey: (await vapid(env)).pub });
  if (url.pathname === "/api/stats" && req.method === "GET") { // 個人を特定しない集計だけ
    const subs = (await env.SUBS.get("count", "json")) || 0, d = day();
    return json({ subscribers: subs, today: (await env.SUBS.get("stat:" + d, "json")) || {} });
  }
  if (req.method !== "POST") return json({ error: "method" }, 405);
  let b;
  try { b = await req.json(); } catch { return json({ error: "json" }, 400); }
  if (url.pathname === "/api/event") { // 通知を開いた回数だけ数える
    if (b && b.type === "open") await bump(env, "open");
    return json({ ok: true });
  }
  if (!b || !validEndpoint(b.endpoint)) return json({ error: "endpoint" }, 400);
  const key = "sub:" + (await hash(b.endpoint));
  if (url.pathname === "/api/subscribe") {
    const count = (await env.SUBS.get("count", "json")) || 0;
    if (!(await env.SUBS.get(key)) ) {
      if (count >= MAX_SUBS) return json({ error: "full" }, 503);
      await env.SUBS.put("count", JSON.stringify(count + 1));
    }
    await env.SUBS.put(key, JSON.stringify({ endpoint: b.endpoint, at: day() }));
    return json({ ok: true });
  }
  if (url.pathname === "/api/unsubscribe") {
    if (await env.SUBS.get(key)) {
      await env.SUBS.delete(key);
      const count = (await env.SUBS.get("count", "json")) || 1;
      await env.SUBS.put("count", JSON.stringify(Math.max(0, count - 1)));
    }
    return json({ ok: true });
  }
  return json({ error: "not found" }, 404);
}

export default {
  async fetch(req, env) {
    const url = new URL(req.url);
    if (url.pathname.startsWith("/api/")) return api(req, env, url);
    return env.ASSETS.fetch(req);
  },
  async scheduled(_event, env, ctx) {
    ctx.waitUntil(tick(env));
  },
};
