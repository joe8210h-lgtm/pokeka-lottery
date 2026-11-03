/* ラッフレアの service worker。オフラインでも前回の画面を開けるようにする。
 * 画面(HTML)とデータ(data/*.json)は「ネットワーク優先」: 通信できるときは必ず最新を取り、できないときだけ保存したものを出す。
 * 画像・アイコンは「保存優先」(裏で更新)。他のサイト(フォントなど)には触れない。
 * 変更したら VERSION を上げる(古い保存は自動で消える)。 */
importScripts("notify-core.js");
const VERSION = "raffrare-v2";
const SHELL = ["./", "index.html", "privacy.html", "manifest.webmanifest", "notify-core.js", "assets/icons/icon-192.png"];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(VERSION).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (e) => {
  e.waitUntil(caches.keys().then((ks) => Promise.all(ks.filter((k) => k !== VERSION).map((k) => caches.delete(k)))).then(() => self.clients.claim()));
});

async function networkFirst(req) {
  const c = await caches.open(VERSION);
  try {
    const res = await fetch(req, { cache: "no-store" });
    if (res.ok) c.put(req, res.clone());
    return res;
  } catch (err) {
    const hit = await c.match(req, { ignoreSearch: true });
    if (hit) return hit;
    throw err;
  }
}

async function staleWhileRevalidate(req) {
  const c = await caches.open(VERSION);
  const hit = await c.match(req);
  const net = fetch(req).then((res) => { if (res.ok) c.put(req, res.clone()); return res; }).catch(() => hit);
  return hit || net;
}

self.addEventListener("fetch", (e) => {
  const req = e.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return;
  if (req.mode === "navigate" || url.pathname.endsWith(".json") || url.pathname.endsWith(".html")) {
    e.respondWith(networkFirst(req));
  } else if (url.pathname.includes("/assets/")) {
    e.respondWith(staleWhileRevalidate(req));
  }
});

/* ---- 通知(Web Push) ----
 * サーバーからの合図は中身なし。ここで最新データと端末内の設定を読み、通知するかを決める(判定は notify-core.js)。
 * Chromeは、合図を受けて何も表示しないと「バックグラウンドで更新しました」と勝手に出す。そのため、出すものが無いときは、一瞬表示してすぐ閉じる。 */
async function onPush() {
  const [prefs, my, hist, follow, notified, counts] = await Promise.all(["prefs", "my", "hist", "follow", "notified", "counts"].map((k) => RaffNotify.kvGet(k)));
  let out = { show: [], mark: [], badge: 0 };
  try {
    const res = await fetch("data/lotteries.json", { cache: "no-store" });
    if (res.ok) out = RaffNotify.decide({ items: await res.json(), prefs, my, hist, follow, notified, counts, now: Date.now() });
  } catch (e) { /* 通信できなければ、出すものなし */ }
  for (const n of out.show) {
    await self.registration.showNotification(n.title, { body: n.body, tag: n.tag, icon: "assets/icons/icon-192.png", badge: "assets/icons/icon-192.png", data: { url: n.url } });
  }
  if (out.show.length) {
    const day = RaffNotify.jstDay(Date.now());
    await RaffNotify.kvSet("notified", (notified || []).concat(out.mark).slice(-500));
    await RaffNotify.kvSet("counts", { day, n: (counts && counts.day === day ? counts.n : 0) + out.show.length });
  } else {
    await self.registration.showNotification("ラッフレア", { tag: "raffrare-silent", silent: true });
    const ns = await self.registration.getNotifications({ tag: "raffrare-silent" });
    ns.forEach((n) => n.close());
  }
  if (self.navigator && navigator.setAppBadge) { try { out.badge ? await navigator.setAppBadge(out.badge) : await navigator.clearAppBadge(); } catch (e) { /* 非対応 */ } }
}
self.addEventListener("push", (e) => e.waitUntil(onPush()));

self.addEventListener("notificationclick", (e) => {
  e.notification.close();
  const url = new URL((e.notification.data && e.notification.data.url) || "./", self.registration.scope).href;
  e.waitUntil((async () => {
    try { await fetch("/api/event", { method: "POST", body: JSON.stringify({ type: "open" }) }); } catch (err) { /* 数えられなくても動く */ }
    const cs = await self.clients.matchAll({ type: "window", includeUncontrolled: true });
    for (const c of cs) { if ("focus" in c) { await c.focus(); if ("navigate" in c) { try { await c.navigate(url); } catch (err) { /* 同一オリジンのみ */ } } return; } }
    await self.clients.openWindow(url);
  })());
});
