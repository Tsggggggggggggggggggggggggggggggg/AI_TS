import os, re, datetime, time, requests
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
    (r"(GPT|LLM|多模态|Agent|agentic)", 6, "模型与能力升级加速，应用边界扩大"),
    (r"(open\s?source|开源|Apache|MIT License)", 5, "开源释放生态势能，降低进入门槛"),
    (r"(API|接口|SDK|插件|集成|integration)", 4, "集成门槛下降，开发效率提升"),
    (r"(降价|price|pricing|cost|单位成本)", 4, "成本曲线下移，利好中小团队快速落地"),
    (r"(融资|投资|收购|并购|估值|M&A|收并购)", 5, "资本涌入与整合加速，行业格局重塑"),
    (r"(政策|监管|合规|安全|privacy|safety)", 4, "合规与安全成为规模化前提，影响部署节奏"),
]

# ========== 通用工具 ==========
def _now_utc():
    return datetime.datetime.utcnow().replace(tzinfo=tz.tzutc())

def _fmt(dt_utc):
    tz_local = tz.gettz(TIMEZONE)
    return dt_utc.astimezone(tz_local).strftime("%Y-%m-%d %H:%M")

def load_rss_list(path):
    feeds = []
    full = os.path.join(BASE_DIR, path)
    if not os.path.exists(full):
        raise FileNotFoundError(f"RSS file not found: {full}")
    with open(full, "r", encoding="utf-8") as f:
        for line in f:
            s = line.strip()
            if s and not s.startswith("#"):
                feeds.append(s)
    if not feeds:
        raise RuntimeError(f"No RSS feeds in {path}")
    return feeds

def within_days(published_time_struct, days=DAYS_BACK):
    if not published_time_struct:
        return True
    pub_ts = time.mktime(published_time_struct)
    return pub_ts >= time.time() - days * 86400

# ========== 抓正文 + 1句摘要 ==========
def fetch_page_text(url, timeout=20):
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
    # 中英混合的简单句子切分
    sents = re.split(r'(?<=[.!?。！？])\s+', text)
    for s in sents:
        s = s.strip()
        if len(s) > 10:
            return s
    return sents[0] if sents else ""

# ========== 翻译（MyMemory 免费接口）==========
def translate_to_zh(text):
    if not text or re.search(r"[\u4e00-\u9fff]", text):
        # 已经是中文或空
        return text
    try:
        url = "https://api.mymemory.translated.net/get"
        params = {"q": text, "langpair": "en|zh-CN"}
        r = requests.get(url, params=params, timeout=12)
        if r.status_code == 200:
            data = r.json()
            zh = data.get("responseData", {}).get("translatedText", "")
            return zh.strip() or text
    except Exception:
        pass
    return text

# ========== 洞察 ==========
def analyze_insight(title, summary):
    text = f"{title} {summary}"
    best, best_w = None, -1
    extra = None
    for pat, w, msg in KEYWEIGHTS:
        if re.search(pat, text, flags=re.I):
            if w > best_w:
                best, best_w = msg, w
    if re.search(r"(开源|open\s?source)", text, flags=re.I):
        extra = "生态更开放、复用更快，利好开发者与中小团队"
    elif re.search(r"(API|SDK|集成|integration)", text, flags=re.I):
        extra = "接入效率提升，产品整合与交付速度更快"
    elif re.search(r"(price|cost|降价|单位成本)", text, flags=re.I):
        extra = "单位经济性改善，探索与落地更具可行性"
    if best and extra and extra not in best:
        return f"{best}；{extra}"
    return best or "趋势显现，可能引发下一阶段行业变化"

# ========== 主流程 ==========
def collect_items(feeds):
    items = []
    for feed in feeds:
        try:
            d = feedparser.parse(feed)
            for e in d.entries[:MAX_PER_FEED]:
                if not getattr(e, "link", ""):
                    continue
                if hasattr(e, "published_parsed"):
                    if not within_days(e.published_parsed):
                        continue
                    pub_dt = datetime.datetime.fromtimestamp(time.mktime(e.published_parsed), tz=tz.tzutc())
                else:
                    pub_dt = _now_utc()
                items.append({
                    "title": getattr(e, "title", "").strip(),
                    "link": e.link,
                    "source": d.feed.get("title", feed),
                    "published": pub_dt
                })
        except Exception:
            continue
    # 去重（按标题）并按时间降序
    seen, uniq = set(), []
    for it in items:
        if it["title"] and it["title"] not in seen:
            uniq.append(it); seen.add(it["title"])
    uniq.sort(key=lambda x: x["published"], reverse=True)
    return uniq

def render_bilingual(items):
    items = items[:TOP_N]
    end = _now_utc()
    start = end - datetime.timedelta(days=DAYS_BACK)

    lines = [
        f"# {THEME.upper()} 每周情报（双语版） · {_fmt(start)} ~ {_fmt(end)}\n",
        "## Top 20（每条：摘要（原文）+ 摘要（中文）+ 洞察（中文））\n"
    ]

    for i, it in enumerate(items, 1):
        text = fetch_page_text(it["link"])
        brief_en = summarize_1_sentence(text) or "No extractable summary; please read the original."
        brief_zh = translate_to_zh(brief_en)
        insight = analyze_insight(it["title"], brief_en)

        lines.append(f"{i}. **{it['title']}**")
        lines.append(f"摘要（原文）：{brief_en}")
        lines.append(f"摘要（中文）：{brief_zh}")
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
