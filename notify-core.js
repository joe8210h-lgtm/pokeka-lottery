/* 通知の判定(画面・service worker・テストで共有)。通信も画面も使わない純粋な関数と、端末内の保存(IndexedDB)だけ。
 * 通知の判断は端末内で行う。フォロー店舗・条件・応募履歴は、サーバーに送らない。 */
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.RaffNotify = factory();
})(typeof self !== "undefined" ? self : this, function () {
  var HR = 36e5, JST = 9 * HR;
  var REQ = { mynumber_card: "mn", biccamera_card: "bc", aeon_card: "ae", yodobashi_member: "yd" };
  var KINDS = ["new", "deadline", "result", "buy"];
  var DEFAULT_PREFS = {
    on: false, kinds: { new: true, deadline: true, result: true, buy: true },
    onlyEligible: true, onlyFollow: false, quiet: true, quietFrom: 23, quietTo: 7, cap: 5
  };

  function t(s) { var v = s ? Date.parse(s) : NaN; return isNaN(v) ? null : v; }
  function jstHour(now) { return new Date(now + JST).getUTCHours(); }
  function jstDay(now) { return new Date(now + JST).toISOString().slice(0, 10); }

  /* 画面の判定「応募可」と同じ条件: 確認済みの抽選だけを「確認済み」とする */
  function verified(it) {
    return !it.review_needed && (it.confidence == null || it.confidence >= 0.8) && it.source_grade !== "third_party" &&
      ((it.consistency || {}).status === "match");
  }
  function eligible(it, my) {
    if (!my || !my.set) return true; /* マイ設定が未入力なら、絞り込まない */
    var ks = (it.requirements || []).map(function (r) { return r.key; });
    for (var k in REQ) if (ks.indexOf(k) >= 0 && !my[REQ[k]]) return false;
    return true;
  }
  function followed(it, follow) {
    if (!follow || !follow.length) return false;
    return follow.some(function (c) { return (it.shop_name || "").indexOf(c) === 0; });
  }
  function inQuiet(prefs, now) {
    if (!prefs.quiet) return false;
    var h = jstHour(now), a = prefs.quietFrom, b = prefs.quietTo;
    return a > b ? (h >= a || h < b) : (h >= a && h < b);
  }
  function name(it) { return (it.product || "抽選") + "(" + (it.shop_name || "店舗未確認") + ")"; }
  function hoursLeft(ms) { return Math.max(1, Math.ceil(ms / HR)); }

  /* 通知する内容を決める。
   * 入力: items(lotteries.json) / prefs / my(マイ設定) / hist(応募履歴 {id:{st}}) / follow(店舗名の配列) / notified(通知済みキーの配列) / counts({day,n}) / now(ms)
   * 出力: show(表示する通知) / mark(通知済みにするキー) / badge(未確認の新着の数) / deferred(おやすみ時間・上限で見送った数) */
  function decide(a) {
    var prefs = Object.assign({}, DEFAULT_PREFS, a.prefs || {}), now = a.now, notified = {}, items = a.items || [];
    (a.notified || []).forEach(function (k) { notified[k] = 1; });
    var hist = a.hist || {}, out = { show: [], mark: [], badge: 0, deferred: 0 };
    if (!prefs.on) return out;
    var cand = [], news = [];
    items.forEach(function (it) {
      var end = t(it.entry_end), start = t(it.entry_start), seen = t(it.first_seen_at), st = it.status;
      var live = st === "open" || st === "upcoming";
      var pass = eligible(it, a.my) && (!prefs.onlyFollow || followed(it, a.follow)) && !hist[it.id];
      if (prefs.kinds.new && live && pass && !notified[it.id + ":new"] && (seen == null || now - seen < 48 * HR)) {
        if (verified(it)) news.push(it); else out.badge++; /* 未確認の新着は、通知せず、バッジだけ */
      }
      if (prefs.kinds.deadline && st === "open" && pass && verified(it) && end != null && end > now && end - now <= 3 * HR && !notified[it.id + ":dl"]) {
        cand.push({ key: it.id + ":dl", kind: "deadline", id: it.id, tag: "dl-" + it.id,
          title: "締切まで約" + hoursLeft(end - now) + "時間", body: name(it) });
      }
      var h = hist[it.id], rd = t(it.result_date);
      if (prefs.kinds.result && h && (h.st === "applied" || h.st === "pending") && rd != null && rd <= now && now - rd < 48 * HR && !notified[it.id + ":res"]) {
        cand.push({ key: it.id + ":res", kind: "result", id: it.id, tag: "res-" + it.id, title: "当選発表の日です", body: name(it) + " の結果を確認して、履歴に記録しましょう" });
      }
      var pe = t(it.purchase_end);
      if (prefs.kinds.buy && h && h.st === "won" && pe != null && pe > now && pe - now <= 24 * HR && !notified[it.id + ":buy"]) {
        cand.push({ key: it.id + ":buy", kind: "buy", id: it.id, tag: "buy-" + it.id, title: "購入期限まで約" + hoursLeft(pe - now) + "時間", body: name(it) });
      }
    });
    if (news.length === 1) {
      cand.push({ key: news[0].id + ":new", kind: "new", id: news[0].id, tag: "new", title: "新着の抽選", body: name(news[0]) });
    } else if (news.length > 1) { /* 同時の新着は1件にまとめる */
      cand.push({ keys: news.map(function (x) { return x.id + ":new"; }), key: news[0].id + ":new", kind: "new", id: news[0].id, tag: "new",
        title: "新着の抽選 " + news.length + "件", body: (news[0].shop_name || "") + "ほか" });
    }
    if (inQuiet(prefs, now)) { out.deferred = cand.length; return out; } /* おやすみ時間は出さない(通知済みにもしない) */
    var used = a.counts && a.counts.day === jstDay(now) ? a.counts.n : 0, room = Math.max(0, prefs.cap - used);
    cand.sort(function (x, y) { return (x.kind === "new") - (y.kind === "new"); }); /* 自分の応募・締切を先に */
    cand.forEach(function (c) {
      if (room <= 0) { out.deferred++; return; }
      room--;
      out.show.push({ key: c.key, kind: c.kind, id: c.id, tag: c.tag, title: c.title, body: c.body, url: "./?lottery=" + encodeURIComponent(c.id) });
      (c.keys || [c.key]).forEach(function (k) { out.mark.push(k); });
    });
    return out;
  }

  /* 端末内の保存(service worker からも使う) */
  function idb() {
    return new Promise(function (res, rej) {
      var r = indexedDB.open("raffrare", 1);
      r.onupgradeneeded = function () { r.result.createObjectStore("kv"); };
      r.onsuccess = function () { res(r.result); };
      r.onerror = function () { rej(r.error); };
    });
  }
  function kvGet(k) {
    return idb().then(function (db) {
      return new Promise(function (res) {
        var q = db.transaction("kv").objectStore("kv").get(k);
        q.onsuccess = function () { res(q.result); };
        q.onerror = function () { res(undefined); };
      });
    });
  }
  function kvSet(k, v) {
    return idb().then(function (db) {
      return new Promise(function (res) {
        var tx = db.transaction("kv", "readwrite");
        tx.objectStore("kv").put(v, k);
        tx.oncomplete = function () { res(); };
        tx.onerror = function () { res(); };
      });
    });
  }

  return { decide: decide, verified: verified, eligible: eligible, DEFAULT_PREFS: DEFAULT_PREFS, KINDS: KINDS, kvGet: kvGet, kvSet: kvSet, jstDay: jstDay };
});
