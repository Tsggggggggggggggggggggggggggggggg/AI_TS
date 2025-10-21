import os, re, time, hashlib, datetime, textwrap, traceback
from dateutil import tz
import feedparser, requests
from bs4 import BeautifulSoup
from readability import Document

# === 可自定义参数 ===
DAYS_BACK = 7
MAX_PER_FEED = 15        # 每个源最多收多少条
SUMMARY_SENTENCES = 3    # 摘要句子数
TIMEZONE = "Asia/Shanghai"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

def load_rss_list(path="rss.txt"):
    feeds = []
    with open(os.path.join(BASE_DIR, path), "r", encoding="utf-8") as f:
        for line in f:
            line=line.strip()
            if not line or line.startswith("#"): 
                continue
            feeds.append(line)
    return feeds

def within_days(published_time_struct, days=DAYS_BACK):
    if not published_time_struct:
        return True  # 无时间的先纳入
    pub_ts = time.mktime(published_time_struct)
    cutoff = time.time() - days*24*3600
    return pub_ts >= cutoff

def fetch_page_text(url, timeout=15):
    try:
        headers = {"User-Agent": "Mozilla/5.0 (AI-Weekly-Digest)"}
        r = requests.get(url, headers=headers, timeout=timeout)
        r.raise_for_status()
        # readability 提取
        doc = Document(r.text)
        html = doc.summary()
        soup = BeautifulSoup(html, "lxml")
        # 去掉脚注/脚本
        for tag in soup(["script","style","noscript"]):
            tag.decompose()
        text = soup.get_text("\n")
        # 简单清洗
        text = re.sub(r"\n{2,}", "\n", text).strip()
        return text
    except Exception as e:
        return ""

CH_SENT_SPLIT = re.compile(r"(?<=[。！？!?])")

def split_sentences(text):
    # 简单的中英文句子切分
    # 先按中文标点切
    parts = []
    for block in text.split("\n"):
        block = block.strip()
        if not block:
            continue
        # 中文句子
        ch_sents = CH_SENT_SPLIT.split(block)
        for s in ch_sents:
            s = s.strip()
            if not s:
                continue
            # 再对英文用 .!? 做一次粗切
            subs = re.split(r'(?<=[.!?])\s+', s)
            for ss in subs:
                ss = ss.strip()
                if ss:
                    parts.append(ss)
    return parts

def summarize(text, max_sents=SUMMARY_SENTENCES):
    if not text:
        return ""
    sents = split_sentences(text)
    if not sents:
        return ""
    # 提取式：优先取前几句，若太短尝试多取一点
    summary = []
    for s in sents:
        # 过滤过短/噪音行
        if len(s) < 8:
            continue
        summary.append(s)
        if len(summary) >= max_sents:
            break
    if not summary:
        summary = sents[:max_sents]
    return " ".join(summary).strip()

def fmt_time(dt_utc):
    tz_sh = tz.gettz(TIMEZONE)
    return dt_utc.astimezone(tz_sh).strftime("%Y-%m-%d %H:%M")

def collect_items():
    feeds = load_rss_list()
    items = []
    for feed in feeds:
        try:
            d = feedparser.parse(feed)
            for entry in d.entries[:MAX_PER_FEED]:
                # 时间
                if hasattr(entry, "published_parsed"):
                    if not within_days(entry.published_parsed, DAYS_BACK):
                        continue
                    pub_dt = datetime.datetime.fromtimestamp(time.mktime(entry.published_parsed), tz=tz.tzutc())
                else:
                    pub_dt = datetime.datetime.utcnow().replace(tzinfo=tz.tzutc())
                # 链接/标题
                link = getattr(entry, "link", "")
                title = getattr(entry, "title", "").strip()
                source = d.feed.get("title", feed)
                if not link or not title:
                    continue
                items.append({
                    "title": title,
                    "link": link,
                    "source": source,
                    "published": pub_dt
                })
        except Exception as e:
            continue
    # 去重（按标题+域名）
    seen = set()
    uniq = []
    for it in items:
        key = (it["title"], re.sub(r"^https?://(www\.)?","",it["link"].split('/')[2] if it["link"].startswith("http") else it["link"]))
        if key in seen:
            continue
        seen.add(key)
        uniq.append(it)
    # 按时间降序
    uniq.sort(key=lambda x: x["published"], reverse=True)
    return uniq

def make_digest(items):
    week_end = datetime.datetime.utcnow().replace(tzinfo=tz.tzutc())
    week_start = week_end - datetime.timedelta(days=DAYS_BACK)
    title = f"AI 每周情报 · {fmt_time(week_start)} ~ {fmt_time(week_end)}"

    lines = [f"# {title}\n"]
    lines.append("## 本周精选（自动生成，提取式摘要）\n")

    for i, it in enumerate(items, 1):
        text = fetch_page_text(it["link"])
        brief = summarize(text, SUMMARY_SENTENCES) if text else "（未能抽取正文，建议点击原文阅读。）"
        lines.append(f"{i}. **{it['title']}**  \n   来源：{it['source']} ｜ 时间：{fmt_time(it['published'])}  \n   链接：{it['link']}  \n   摘要：{brief}\n")

    # 简单的技术/趋势区块（从摘要里抽关键词的极简替代）
    lines.append("\n---\n**自动提示**：以上为提取式摘要，建议你在发布前快速扫一眼标题与摘要，必要时补充人工一句话点评。")

    out_path = os.path.join(OUTPUT_DIR, "weekly_digest.md")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return out_path

def main():
    items = collect_items()
    # 控制总量，避免过长；可按需调整
    items = items[:40]
    path = make_digest(items)
    print(f"Digest saved -> {path}")

if __name__ == "__main__":
    main()
