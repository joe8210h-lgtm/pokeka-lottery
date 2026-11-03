// 合図(push)を送るかどうかの判定。純粋な関数(テスト可能)。
// 状態 state = { seen: [抽選id], fired: ["id:kind"] }。初回(state が null)は、現在の抽選を既知として記録するだけで、合図は送らない。
const HR = 3600e3;
const ts = (s) => { const v = s ? Date.parse(s) : NaN; return Number.isNaN(v) ? null : v; };

export function computeEvents(items, state, now) {
  const live = items.filter((it) => it.status === "open" || it.status === "upcoming");
  const nextSeen = live.map((it) => it.id);
  if (!state) return { events: [], state: { seen: nextSeen, fired: [] } };
  const seen = new Set(state.seen), fired = new Set(state.fired), events = [];
  for (const it of items) {
    const end = ts(it.entry_end), rd = ts(it.result_date), pe = ts(it.purchase_end);
    if ((it.status === "open" || it.status === "upcoming") && !seen.has(it.id)) events.push({ kind: "new", id: it.id });
    if (it.status === "open" && end && end > now && end - now <= 3 * HR && !fired.has(it.id + ":dl")) { events.push({ kind: "deadline", id: it.id }); fired.add(it.id + ":dl"); }
    if (rd && rd <= now && now - rd < 24 * HR && !fired.has(it.id + ":res")) { events.push({ kind: "result", id: it.id }); fired.add(it.id + ":res"); }
    if (pe && pe > now && pe - now <= 24 * HR && !fired.has(it.id + ":buy")) { events.push({ kind: "buy", id: it.id }); fired.add(it.id + ":buy"); }
  }
  const ids = new Set(items.map((it) => it.id));
  return { events, state: { seen: nextSeen, fired: [...fired].filter((k) => ids.has(k.split(":")[0])) } };
}

// Web Push の宛先として許す送信先(任意のURLへ送らせない)
const PUSH_HOSTS = [/(^|\.)fcm\.googleapis\.com$/, /(^|\.)push\.services\.mozilla\.com$/, /(^|\.)push\.apple\.com$/, /(^|\.)notify\.windows\.com$/];
export function validEndpoint(s) {
  if (typeof s !== "string" || s.length > 800) return false;
  let u;
  try { u = new URL(s); } catch { return false; }
  return u.protocol === "https:" && !u.username && !u.password && PUSH_HOSTS.some((re) => re.test(u.hostname));
}
