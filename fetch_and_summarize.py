import os, re, time, datetime
from dateutil import tz
import feedparser, requests
from bs4 import BeautifulSoup
from readability import Document

DAYS_BACK = int(os.getenv("DAYS_BACK", "7"))
MAX_PER_FEED = int(os.getenv("MAX_PER_FEED", "15"))
SUMMARY_SENTENCES = int(os.getenv("SUMMARY_SENTENCES", "3"))
TIMEZONE = os.getenv("TIMEZONE", "Asia/Shanghai")

THEME = os.getenv("THEME", "ai").strip().lower()
RSS_FILE = os.getenv("RSS_FILE", f"rss_{THEME}.txt")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

def load_rss_list(path):
    feeds = []
    full = os.path.join(BASE_DIR, path)
    if not os.path.exists(full):
        raise FileNotFoundError(f"RSS file not found: {full}")
    with open(full, "r", encoding="utf-8") as f:
        for line in f:
            line=line.strip()
            if not line or line.startswith("#"): 
                continue
            feeds.append(line)
    if not feeds:
        raise RuntimeError(f"No RSS feeds found in {path}")
    return feeds

def within_days(published_time_struct, days=DAYS_BACK):
    if not published_time_struct:
        return True
    import time as _t
    pub_ts = _t.mktime(published_time_struct)
    cutoff = _t.time() - days*24*3600
    return pub_ts >= cutoff

def fetch_page_text(url, timeout=15):
    try:
        headers = {"User-Agent": "Mozilla/5.0 (AI-Weekly-Digest)"}
        r = requests.get(url, headers=headers, timeout=timeout)
        r.raise_for_status()
        doc = Document(r.text)
        html = doc.summary()
        soup = BeautifulSoup(html, "lxml")
        for tag in soup(["script","style","noscript"]):
            tag.decompose()
        text = soup.get_text("\n")
        import re as _re
        text = _re.sub(r"\n{2,}", "\n", text).strip()
        return text
    except Exception:
        return ""

import re as _re
CH_SENT_SPLIT = _re.compile(r"(?<=[。！？!?])")

def split_sentences(text):
    parts = []
    for block in text.split("\n"):
        block = block.strip()
        if not block:
            continue
        ch_sents = CH_SENT_SPLIT.split(block)
        for s in ch_sents:
            s = s.strip()
            if not s:
                continue
            subs = _re.split(r'(?<=[.!?])\s+', s)
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
    summary = []
    for s in sents:
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

def collect_items(feeds):
    import time as _t
    items = []
    for feed in feeds:
        try:
            d = feedparser.parse(feed)
            for entry in d.entries[:MAX_PER_FEED]:
                if hasattr(entry, "published_parsed"):
                    if not within_days(entry.published_parsed, DAYS_BACK):
                        continue
                    pub_dt = datetime.datetime.fromtimestamp(_t.mktime(entry.published_parsed), tz=tz.tzutc())
                else:
                    pub_dt = datetime.datetime.utcnow().replace(tzinfo=tz.tzutc())
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
        except Exception:
            continue
    seen = set()
    uniq = []
    for it in items:
        domain = it["link"]
        if it["link"].startswith("http"):
            try:
                domain = _re.sub(r"^https?://(www\.)?","",it["link"].split('/')[2])
            except Exception:
                domain = it["link"]
        key = (it["title"], domain)
        if key in seen:
            continue
        seen.add(key)
        uniq.append(it)
    uniq.sort(key=lambda x: x["published"], reverse=True)
    return uniq

def make_digest(items):
    week_end = datetime.datetime.utcnow().replace(tzinfo=tz.tzutc())
    week_start = week_end - datetime.timedelta(days=DAYS_BACK)
    title = f"{THEME.upper()} 每周情报 · {fmt_time(week_start)} ~ {fmt_time(week_end)}"

    lines = [f"# {title}\n"]
    lines.append("## 本周精选（自动生成，提取式摘要）\n")

    for i, it in enumerate(items, 1):
        text = fetch_page_text(it["link"])
        brief = summarize(text, SUMMARY_SENTENCES) if text else "（未能抽取正文，建议点击原文阅读。）"
        lines.append(f"{i}. **{it['title']}**  \n   来源：{it['source']} ｜ 时间：{fmt_time(it['published'])}  \n   链接：{it['link']}  \n   摘要：{brief}\n")

    lines.append("\n---\n**自动提示**：以上为提取式摘要，发布前可快速校对。")
    out_name = f"weekly_digest_{THEME}.md"
    out_path = os.path.join(OUTPUT_DIR, out_name)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"Digest saved -> {out_path}")

def main():
    feeds = load_rss_list(RSS_FILE)
    items = collect_items(feeds)[:40]
    make_digest(items)

if __name__ == "__main__":
    main()
