import os, re, datetime
from dateutil import tz
import feedparser, requests
from bs4 import BeautifulSoup
from readability import Document

# ====== 可调参数 ======
DAYS_BACK = int(os.getenv("DAYS_BACK", "7"))     # 抓取最近 N 天
MAX_PER_FEED = int(os.getenv("MAX_PER_FEED", "40"))
SUMMARY_SENTENCES = 1                            # 模式一：只输出 1 句摘要
TOP_N = 20                                       # 每个主题只保留前 20 条
TIMEZONE = os.getenv("TIMEZONE", "Asia/Shanghai")

# 主题：ai / business / psych / design （由 workflow 传入）
THEME = os.getenv("THEME", "ai").strip().lower()
RSS_FILE = os.getenv("RSS_FILE", f"rss_{THEME}.txt")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ====== 关键词权重（影响排序 & 洞察）======
KEYWEIGHTS = [
    (r"(GPT|LLM|大模型|multimodal|多模态|Agent)", 6, "模型与能力升级加速，应用边界扩大", "Model capabilities are ramping up, widening real-world use cases"),
    (r"(open\s?source|开源|Apache|MIT License)", 5, "开源释放生态势能，降低进入门槛", "Open-source momentum lowers entry barriers and grows the ecosystem"),
    (r"(API|接口|SDK|插件|集成)", 4, "更易于二次开发与集成，利好开发者生态", "Easier integration/API access speeds product shipping for developers"),
    (r"(降价|price cut|cost|成本|便宜)", 5, "成本曲线下移，商用落地节奏加快", "Falling costs accelerate commercialization and experiments"),
    (r"(融资|收购|并购|acquire|funding|投资|估值)", 5, "资本与产业集中，行业版图重组", "Capital flows and M&A reshape the competitive landscape"),
    (r"(政策|监管|合规|regulation|privacy|安全|安全性)", 4, "合规与安全成为规模化前提", "Compliance and safety are prerequisites for scaling"),
    (r"(芯片|GPU|算力|推理|训练|throughput|latency)", 5, "算力与效率影响产品体验与成本", "Compute efficiency directly impacts UX and unit economics"),
    (r"(伙伴|合作|partnership|生态|生态计划|开发者)", 3, "生态协作放大网络效应", "Partnerships amplify network effects"),
    (r"(生产力|办公|教育|工业|医疗|金融|制造|物流)", 3, "垂直场景加速，需求更清晰", "Vertical adoption is accelerating with clearer ROI"),
]

# ====== 工具函数 ======
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
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            feeds.append(line)
    if not feeds:
        raise RuntimeError(f"No RSS feeds in {path}")
    return feeds

def within_days(published_time_struct, days=DAYS_BACK):
    if not published_time_struct:
        return True
    import time as _t
    pub_ts = _t.mktime(published_time_struct)
    cutoff = _t.time() - days * 24 * 3600
    return pub_ts >= cutoff

def fetch_page_text(url, timeout=15):
    try:
        headers = {"User-Agent": "Mozilla/5.0 (AI-Weekly-Digest)"}
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

# ====== 句子切分 + 1句摘要 ======
CH_SPLIT = re.compile(r"(?<=[。！？!?])")
def split_sentences(text):
    parts = []
    for block in text.split("\n"):
        b = block.strip()
        if not b:
            continue
        ch_sents = CH_SPLIT.split(b)
        for s in ch_sents:
            s = s.strip()
            if not s:
                continue
            subs = re.split(r'(?<=[.!?])\s+', s)
            for ss in subs:
                ss = ss.strip()
                if ss:
                    parts.append(ss)
    return parts

def summarize_1_sentence(text):
    if not text:
        return ""
    sents = split_sentences(text)
    for s in sents:
        if len(s) >= 8:
            return s
    return sents[0] if sents else ""

# ====== 打分（时间 + 关键词权重）======
def score_item(title, published):
    now = _now_utc()
    days = (now - published).total_seconds() / 86400
    time_score = max(0, 7 - days)  # 0~7
    kw_score = 0
    for pat, w, _, _ in KEYWEIGHTS:
        if re.search(pat, title, flags=re.I):
            kw_score += w
    return time_score + kw_score

# ====== 洞察（中/英）======
def why_it_matters_zh(title, summary):
    text = f"{title} {summary}"
    best, best_w = None, -1
    extra = None
    for pat, w, hint_zh, _ in KEYWEIGHTS:
        if re.search(pat, text, flags=re.I):
            if w > best_w:
                best, best_w = hint_zh, w
    if re.search(r"(降价|price|cost|便宜)", text, flags=re.I):
        extra = "降低试错成本，有利于中小团队快速落地"
    elif re.search(r"(开源|open\s?source)", text, flags=re.I):
        extra = "生态更开放，复用与二开更容易"
    elif re.search(r"(API|SDK|接口|集成)", text, flags=re.I):
        extra = "接入门槛下降，产品整合速度提升"
    elif re.search(r"(融资|收购|并购|acquire|funding|估值)", text, flags=re.I):
        extra = "产业集中趋势明显，头部优势扩大"
    elif re.search(r"(监管|合规|regulation|隐私|安全)", text, flags=re.I):
        extra = "合规风险需提前评估，部署节奏可能受影响"
    if best and extra and extra not in best:
        return f"{best}；{extra}"
    if best:
        return best
    return "该方向活跃度提升，或将催化相关应用/投资机会"

def why_it_matters_en(title, summary):
    text = f"{title} {summary}"
    best, best_w = None, -1
    extra = None
    for pat, w, _, hint_en in KEYWEIGHTS:
        if re.search(pat, text, flags=re.I):
            if w > best_w:
                best, best_w = hint_en, w
    if re.search(r"(降价|price|cost|便宜|pricing)", text, flags=re.I):
        extra = "Lower trial costs—great for smaller teams to ship faster"
    elif re.search(r"(开源|open\s?source)", text, flags=re.I):
        extra = "More open ecosystem—reuse and forks get easier"
    elif re.search(r"(API|SDK|接口|集成|integration)", text, flags=re.I):
        extra = "Lower integration friction—products ship quicker"
    elif re.search(r"(融资|收购|并购|acquire|funding|估值|M&A)", text, flags=re.I):
        extra = "Consolidation is underway—leaders expand the moat"
    elif re.search(r"(监管|合规|regulation|privacy|安全|safety)", text, flags=re.I):
        extra = "Compliance risk needs early planning—may affect rollout pace"
    if best and extra and extra not in best:
        return f"{best}. {extra}"
    if best:
        return best
    return "Momentum is building—likely to catalyze apps and investment"

# ====== 主流程 ======
def collect_items(feeds):
    items = []
    for feed in feeds:
        try:
            d = feedparser.parse(feed)
            for e in d.entries[:MAX_PER_FEED]:
                if hasattr(e, "published_parsed"):
                    if not within_days(e.published_parsed, DAYS_BACK):
                        continue
                    import time as _t
                    pub_dt = datetime.datetime.fromtimestamp(_t.mktime(e.published_parsed), tz=tz.tzutc())
                else:
                    pub_dt = _now_utc()
                link = getattr(e, "link", "")
                title = getattr(e, "title", "").strip()
                source = d.feed.get("title", feed)
                if not link or not title:
                    continue
                items.append({"title": title, "link": link, "source": source, "published": pub_dt})
        except Exception:
            continue
    # 去重（标题+域名）
    seen, uniq = set(), []
    for it in items:
        domain = it["link"]
        if it["link"].startswith("http"):
            try:
                domain = re.sub(r"^https?://(www\.)?", "", it["link"].split('/')[2])
            except Exception:
                pass
        key = (it["title"], domain)
        if key in seen:
            continue
        seen.add(key)
        uniq.append(it)
    # 打分排序
    for it in uniq:
        it["_score"] = score_item(it["title"], it["published"])
    uniq.sort(key=lambda x: x["_score"], reverse=True)
    return uniq

def render_zh(items):
    week_end = _now_utc()
    week_start = week_end - datetime.timedelta(days=DAYS_BACK)
    title = f"{THEME.upper()} 每周情报 · {_fmt(week_start)} ~ {_fmt(week_end)}"
    lines = [f"# {title}\n", "## 本周 Top 20（每条 1 句摘要 + 1 句洞察）\n"]
    for i, it in enumerate(items, 1):
        text = fetch_page_text(it["link"])
        brief = summarize_1_sentence(text) or "（正文抽取失败，建议看原文）"
        insight = why_it_matters_zh(it["title"], brief)
        lines.append(
            f"{i}. **{it['title']}**  \n"
            f"   摘要：{brief}  \n"
            f"   洞察：{insight}  \n"
            f"   来源：{it['source']} ｜ 时间：{_fmt(it['published'])}  \n"
            f"   链接：{it['link']}\n"
        )
    return "\n".join(lines)

def render_en(items):
    week_end = _now_utc()
    week_start = week_end - datetime.timedelta(days=DAYS_BACK)
    title = f"{THEME.upper()} Weekly Brief · {_fmt(week_start)} ~ {_fmt(week_end)}"
    lines = [f"# {title}\n", "## Top 20 (1-line TL;DR + Why it matters)\n"]
    for i, it in enumerate(items, 1):
        text = fetch_page_text(it["link"])
        # 简洁英文 TL;DR（若正文是中文，也给一个自然英文 recap）
        brief_src = summarize_1_sentence(text)
        if not brief_src or re.search(r"[\u4e00-\u9fff]", brief_src):
            # 给一个自然英文 recap：Title + soft verb
            brief_en = f"{it['title']}: key updates worth a look."
        else:
            brief_en = brief_src
        insight_en = why_it_matters_en(it["title"], brief_src or it["title"])
        lines.append(
            f"{i}. **{it['title']}**  \n"
            f"   TL;DR: {brief_en}  \n"
            f"   Why it matters: {insight_en}  \n"
            f"   Source: {it['source']} · Time: {_fmt(it['published'])}  \n"
            f"   Link: {it['link']}\n"
        )
    return "\n".join(lines)

def make_digest(items):
    # 只取 Top N
    items = items[:TOP_N]

    zh = render_zh(items)
    en = render_en(items)

    zh_path = os.path.join(OUTPUT_DIR, f"weekly_digest_{THEME}_zh.md")
    en_path = os.path.join(OUTPUT_DIR, f"weekly_digest_{THEME}_en.md")
    bi_path = os.path.join(OUTPUT_DIR, f"weekly_digest_{THEME}_bilingual.md")

    with open(zh_path, "w", encoding="utf-8") as f:
        f.write(zh)
    with open(en_path, "w", encoding="utf-8") as f:
        f.write(en)
    with open(bi_path, "w", encoding="utf-8") as f:
        f.write(zh + "\n\n---\n\n" + en)

    print(f"Saved -> {zh_path}")
    print(f"Saved -> {en_path}")
    print(f"Saved -> {bi_path}")

def main():
    feeds = load_rss_list(RSS_FILE)
    items = collect_items(feeds)
    make_digest(items)

if __name__ == "__main__":
    main()
