"""公開用の説明文(summary)を、schemaの項目だけから作る(CLAUDE.md 16番)。
他サイトの文章は入力に使わない。語順は固定: 店舗、商品、受付方法、受付期間、当選発表、必要なもの。
断定できない項目は「未確認」と書く。文は120字程度に収める。"""
from datetime import datetime, timedelta, timezone

JST = timezone(timedelta(hours=9))
CHANNEL = {"in_store": "店頭受付", "web_form": "Webフォーム", "x_repost": "Xリポスト", "app": "アプリ",
           "invitation": "招待リクエスト", "receipt_upload": "レシート送信"}
WD = "月火水木金土日"
MAX_LEN = 120


def _dt(s):
    try:
        d = datetime.fromisoformat(s)
    except (TypeError, ValueError):
        return None
    return d if d.tzinfo else d.replace(tzinfo=JST)


def _fmt(s, with_time=True):
    d = _dt(s)
    if not d:
        return None
    d = d.astimezone(JST)
    out = f"{d.month}/{d.day}({WD[d.weekday()]})"
    return out + (f" {d.hour}:{d.minute:02d}" if with_time else "")


def make_summary(it):
    shop = it.get("shop_name") or "店舗未確認"
    prod = it.get("product") or "商品未確認"
    ch = CHANNEL.get(it.get("entry_channel"), "未確認")
    s, e = _fmt(it.get("entry_start")), _fmt(it.get("entry_end"))
    if it.get("window_type") == "rolling":
        period = "期間は固定なし" if not s else f"{s}から(終了日なし)"
    elif s and e:
        period = f"{s}〜{e}"
    elif e:
        period = f"開始未確認〜{e}"
    elif s:
        period = f"{s}〜終了未確認"
    else:
        period = "未確認"
    res = _fmt(it.get("result_date"), with_time=False) or "未確認"
    reqs = [r.get("label") for r in (it.get("requirements") or []) if r.get("label")]
    need = "、".join(reqs[:3]) if reqs else "未確認"
    text = f"{shop}の{prod}。{ch}、受付{period}。当選発表{res}。必要なもの: {need}。"
    if len(text) > MAX_LEN + 20:  # 長い店舗名・商品名のとき、必要なものを短くする
        text = f"{shop}の{prod}。{ch}、受付{period}。当選発表{res}。必要なもの: {need[:20]}…" if need != "未確認" else text
    return text
