/* ラッフレアの service worker。オフラインでも前回の画面を開けるようにする。
 * 画面(HTML)とデータ(data/*.json)は「ネットワーク優先」: 通信できるときは必ず最新を取り、できないときだけ保存したものを出す。
 * 画像・アイコンは「保存優先」(裏で更新)。他のサイト(フォントなど)には触れない。
 * 変更したら VERSION を上げる(古い保存は自動で消える)。 */
const VERSION = "raffrare-v1";
const SHELL = ["./", "index.html", "privacy.html", "manifest.webmanifest", "assets/icons/icon-192.png"];

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
