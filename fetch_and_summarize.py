import os, re, datetime, time, json, requests
from dateutil import tz
import feedparser
from bs4 import BeautifulSoup
from readability import Document

# ========== 参数 ==========
DAYS_BACK = int(os.getenv("DAYS_BACK", "7"))
MAX_PER_FEED = int(os.getenv("MAX_PER_FEED", "40"))
TOP_N = int(os.getenv("TOP_N", "20"))
TIMEZONE = os.getenv("TIMEZONE", "Asia/Shanghai")
THEME = os.getenv("THEME", "ai").strip().lower()
RSS_FILE = os.getenv("RSS_FILE", f"rss_{THEME}.txt")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ========== 关键词洞察 ==========
KEYWEIGHTS = [
    (r"(GPT|LLM|多模态|Agent)", 6, "模型与能力升级加速，应用边界扩大"),
    (r"(open\s?source|开源)", 5, "开源释放生态势能，降低进入门槛"),
    (r"(API|接口|SDK|插件|集成)", 4, "集成门槛下降，开发效率提升"),
    (r"(降价|price|cost)", 4, "成本曲线下移，有利于中小团队落地"),
    (r"(融资|投资|收购|并购|估值)", 5, "资本涌入，行业格局加速洗牌"),
    (r"(政策|监管|合规|安全|privacy)", 4, "合规成为规模化前提，安全是信任基础"),
]

# ========== 通用工具 ==========
def _now_utc():
    return datetime.datetime.utcnow().replace(tzinfo=tz.tzutc())

def _fmt(dt_utc):
    tz_local = tz.gettz(TIMEZONE)
    return dt_utc.astimezone(tz_local).strftime("%Y-%m-%d %H:%M")

def load_rss_list(path):
    feeds = []
    with open(os.path.join(BASE_DIR, path), "r", encoding="utf-8") as f:
        for line in f:
            if line.strip() and not line.startswith("#"):
                feeds.append(line.strip())
    return feeds

def within_days(published_time_struct, days=DAYS_BACK):
    if not published_time_struct:
        return True
    pub_ts = time.mktime(published_time_struct)
    return pub_ts >= time.time() - days * 86400

# ========== 抓正文 + 摘要 ==========
def fetch_page_text(url, timeout=12):
    try:
        headers = {"User-Agent": "Mozilla/5.0 (AI-WeeklyDigest)"}
        r = requests.get(url, headers=headers, timeout=timeout)
        r.raise_for_status()
        doc = Document(r.text)
        html = doc.summary()
        soup = BeautifulSoup(html, "lxml")
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()
        text = soup.get_text("\n")
        text = re.sub(r"\n{2,}", "\n", text).strip()
        return text
    except Exception:
        return ""

def summarize_1_sentence(text):
    if not text:
        return ""
    sents = re.split(r'(?<=[.!?。！？])\s+', text)
    for s in sents:
        if len(s.strip()) > 10:
            return s.strip()
    return sents[0] if sents else ""

# ========== 翻译 ==========
def translate_to_zh(text):
    """使用 MyMemory 免费翻译 API 自动翻译为中文"""
    if not text.strip():
        return ""
    try:
        url = f"https://api.mymemory.translated.net/get?q={text}&langpair=en|zh-CN"
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            data = r.json()
            return data.get("responseData", {}).get("translatedText", "").strip()
    except Exception:
        pass
    return text  # 翻译失败回原文

# ========== 洞察 ==========
def analyze_insight(title, summary):
    text = f"{title} {summary}"
    for pat, w, msg in KEYWEIGHTS:
        if re.search(pat, text, flags=re.I):
            return msg
    return "趋势显现，可能引发下一阶段行业变革"

# ========== 主体 ==========
def collect_items(feeds):
    items = []
    for feed in feeds:
        d = feedparser.parse(feed)
        for e in d.entries[:MAX_PER_FEED]:
            if not hasattr(e, "link"):
                continue
            if hasattr(e, "published_parsed"):
                if not within_days(e.published_parsed):
                    continue
                pub_dt = datetime.datetime.fromtimestamp(time.mktime(e.published_parsed), tz=tz.tzutc())
            else:
                pub_dt = _now_utc()
            items.append({
                "title": e.title,
                "link": e.link,
                "source": d.feed.get("title", feed),
                "published": pub_dt
            })
    # 去重 + 排序
    seen, uniq = set(), []
    for it in items:
        if it["title"] not in seen:
            uniq.append(it)
            seen.add(it["title"])
    uniq.sort(key=lambda x: x["published"], reverse=True)
    return uniq

def render_bilingual(items):
    items = items[:TOP_N]
    end = _now_utc()
    start = end - datetime.timedelta(days=DAYS_BACK)
    lines = [f"# {THEME.upper()} 每周情报（双语版） · {_fmt(start)} ~ {_fmt(end)}\n"]

    for i, it in enumerate(items, 1):
        text = fetch_page_text(it["link"])
        summary_en = summarize_1_sentence(text) or "No extractable summary; please read the original."
        summary_zh = translate_to_zh(summary_en)
        insight = analyze_insight(it["title"], summary_en)

        lines.append(f"{i}. **{it['title']}**")
        lines.append(f"摘要（原文）：{summary_en}")
        lines.append(f"摘要（中文）：{summary_zh}")
        lines.append(f"洞察（中文）：{insight}")
        lines.append(f"来源：{it['source']} ｜ 时间：{_fmt(it['published'])}")
        lines.append(f"链接：{it['link']}\n")

    return "\n".join(lines)

def main():
    feeds = load_rss_list(RSS_FILE)
    items = collect_items(feeds)
    report = render_bilingual(items)
    out = os.path.join(OUTPUT_DIR, f"weekly_digest_{THEME}_bilingual.md")
    with open(out, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"✅ Saved bilingual digest -> {out}")

if __name__ == "__main__":
    main()
