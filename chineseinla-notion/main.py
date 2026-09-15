import csv
import os
import re
import time
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

# =========================
# SETTINGS
# =========================
DAYS_TO_KEEP = 2
APPLY_FILTERS = True
MAX_PAGES = 150
STOP_AFTER_EMPTY_RECENT_PAGES = 2
REQUEST_DELAY_SECONDS = 0.8

START_URL = "https://www.chineseinla.com/f/page_viewforum/f_29.html"
LA_TZ = ZoneInfo("America/Los_Angeles")
OUTPUT_DIR = Path(__file__).resolve().parent / "output"

NOTION_TOKEN = os.environ.get("NOTION_TOKEN", "").strip()
NOTION_PAGE_ID = "3dbc18c6fba48086a663f8fe7d77a9a3"
NOTION_VERSION = "2022-06-28"

if not NOTION_TOKEN:
    raise RuntimeError("Missing GitHub Actions secret: NOTION_TOKEN")
if not NOTION_TOKEN.startswith("ntn_"):
    raise RuntimeError("NOTION_TOKEN should start with ntn_")
NOTION_TOKEN.encode("ascii")

# =========================
# FILTERS
# =========================
FORCE_KEEP_KEYWORDS = [
    "幼儿园", "preschool", "daycare",
    "设备维保", "设备维护", "设备维修", "机修",
    "maintenance technician", "maintenance mechanic",
]

REMOVE_RULES = {
    "求职帖": [
        "求职", "本人找工作", "本人求工作", "寻找工作", "寻工作",
        "求兼职", "求全职",
    ],
    "保险类": [
        "保险", "insurance agent", "insurance broker",
        "保险经纪", "保险代理", "兼职写单", "写单人员",
    ],
    "Uber/Lyft": ["uber", "lyft", "网约车司机"],
    "牙科/医疗工作人员": [
        "牙科", "牙医", "dental assistant", "dental receptionist",
        "dental office", "护士", "护理员", "护理人员", "lvn", "cna",
        "medical assistant", "医疗助理", "诊所前台",
    ],
    "培训/招生/明显营销": [
        "包教包会包就业", "包教包会", "包就业", "培训班", "考试培训",
        "考证培训", "招生", "轻松月入", "零基础创业", "免费创业",
    ],
    "个人接活/服务广告": [
        "上门维修", "承接装修", "装修服务", "搬家服务", "个人接活",
    ],
}

# =========================
# HTTP
# =========================
session = requests.Session()
session.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/142.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
})

TIME_PATTERN = re.compile(
    r"\b(1[0-2]|0?[1-9]):([0-5][0-9])\s*(am|pm)\b", re.IGNORECASE
)
DATE_PATTERN = re.compile(r"\b(20\d{2}-\d{2}-\d{2})\b")


def clean_text(text):
    if not text:
        return ""
    return re.sub(r"\s+", " ", text.replace("\u00a0", " ")).strip()


def date_window():
    today = datetime.now(LA_TZ).date()
    cutoff = today - timedelta(days=max(DAYS_TO_KEEP, 1) - 1)
    return today, cutoff


def extract_post_date(context):
    """Today appears as am/pm; older posts appear as YYYY-MM-DD."""
    today, cutoff = date_window()

    tm = TIME_PATTERN.search(context)
    if tm:
        hour = int(tm.group(1))
        minute = int(tm.group(2))
        am_pm = tm.group(3).lower()
        if am_pm == "am":
            hour24 = 0 if hour == 12 else hour
        else:
            hour24 = 12 if hour == 12 else hour + 12
        return {
            "post_date": today.isoformat(),
            "display_time": tm.group(0),
            "time_24": f"{hour24:02d}:{minute:02d}",
        }

    matches = DATE_PATTERN.findall(context)
    for date_string in reversed(matches):
        try:
            post_date = datetime.strptime(date_string, "%Y-%m-%d").date()
        except ValueError:
            continue
        if cutoff <= post_date <= today:
            return {
                "post_date": post_date.isoformat(),
                "display_time": "",
                "time_24": "00:00",
            }
        if post_date < cutoff:
            return None
    return None


def get_page(url):
    response = session.get(url, timeout=30, allow_redirects=True)
    response.raise_for_status()
    if not response.encoding or response.encoding.lower() == "iso-8859-1":
        response.encoding = response.apparent_encoding
    return response


def topic_context(anchor):
    tr = anchor.find_parent("tr")
    if tr:
        return clean_text(tr.get_text(" ", strip=True))
    li = anchor.find_parent("li")
    if li:
        return clean_text(li.get_text(" ", strip=True))

    node = anchor
    title = clean_text(anchor.get_text(" ", strip=True))
    best = ""
    for _ in range(7):
        node = node.parent
        if node is None:
            break
        text = clean_text(node.get_text(" ", strip=True))
        if len(text) >= len(title) and len(text) < 1000:
            best = text
    return best


def start_number(url):
    match = re.search(r"/start_(\d+)\.html", url)
    if match:
        return int(match.group(1))
    if "page_viewforum/f_29.html" in url:
        return 0
    return None


def next_page(soup, current_url):
    links = []
    for a in soup.select('a[href*="page_viewforum"]'):
        text = clean_text(a.get_text(" ", strip=True))
        href = a.get("href", "")
        if href:
            links.append((text, urljoin(current_url, href)))

    for text, href in links:
        if (
            "下一页" in text
            or "next" in text.lower()
            or text in [">", "›", "»", "→"]
        ) and href != current_url:
            return href

    current = start_number(current_url) or 0
    candidates = []
    for _, href in links:
        n = start_number(href)
        if n is not None and n > current:
            candidates.append((n, href))
    if not candidates:
        return None
    return sorted(candidates, key=lambda x: x[0])[0][1]


def classify(topic):
    text = clean_text(f"{topic['title']} {topic['context']}").lower()

    for keyword in FORCE_KEEP_KEYWORDS:
        if keyword.lower() in text:
            return True, "强制保留"

    if not APPLY_FILTERS:
        return True, "未筛选"

    for reason, keywords in REMOVE_RULES.items():
        for keyword in keywords:
            if keyword.lower() in text:
                return False, reason

    return True, "保留"


def scrape():
    today, cutoff = date_window()
    print(f"Keep dates: {cutoff} -> {today} (America/Los_Angeles)")

    current_url = START_URL
    page_number = 1
    seen_links = set()
    recent = []
    seen_recent = False
    empty_pages = 0

    while page_number <= MAX_PAGES:
        print(f"Page {page_number}: {current_url}")
        response = get_page(current_url)
        soup = BeautifulSoup(response.text, "html.parser")
        anchors = soup.select('a[href*="page_viewtopic"]')
        print("topic links:", len(anchors))

        if not anchors:
            OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            (OUTPUT_DIR / "debug_no_topics.html").write_text(
                response.text, encoding="utf-8"
            )
            raise RuntimeError("HTTP succeeded but no topic links were parsed")

        page_recent = 0
        page_seen = set()

        for anchor in anchors:
            title = clean_text(anchor.get_text(" ", strip=True))
            href = anchor.get("href", "")
            if not title or not href:
                continue

            href = urljoin(current_url, href)
            if "page_viewtopic" not in href or href in page_seen:
                continue
            page_seen.add(href)

            context = topic_context(anchor)
            info = extract_post_date(context)
            if not info:
                continue

            page_recent += 1
            if href in seen_links:
                continue
            seen_links.add(href)

            recent.append({
                "page": page_number,
                "title": title,
                "context": context,
                "link": href,
                "post_date": info["post_date"],
                "display_time": info["display_time"],
                "time_24": info["time_24"],
            })

        print("recent on page:", page_recent, "total:", len(recent))

        if page_recent:
            seen_recent = True
            empty_pages = 0
        elif seen_recent:
            empty_pages += 1

        if seen_recent and empty_pages >= STOP_AFTER_EMPTY_RECENT_PAGES:
            print("Reached older content; stop.")
            break

        nxt = next_page(soup, current_url)
        if not nxt or nxt == current_url:
            break

        current_url = nxt
        page_number += 1
        time.sleep(REQUEST_DELAY_SECONDS)

    if not recent:
        raise RuntimeError("No recent posts found; Notion will not be changed")

    recent.sort(
        key=lambda x: (x["post_date"], x["time_24"]), reverse=True
    )
    return recent


def filter_topics(topics):
    kept, removed = [], []
    reasons = Counter()

    for topic in topics:
        keep, reason = classify(topic)
        item = dict(topic)
        item["filter_reason"] = reason
        if keep:
            kept.append(item)
        else:
            removed.append(item)
            reasons[reason] += 1

    return kept, removed, reasons


def save_csv(name, topics):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    fields = [
        "post_date", "display_time", "page", "title", "link",
        "filter_reason", "context",
    ]
    with open(OUTPUT_DIR / name, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for topic in topics:
            writer.writerow({k: topic.get(k, "") for k in fields})


# =========================
# NOTION
# =========================
NOTION_HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": NOTION_VERSION,
    "Content-Type": "application/json",
}


def notion_request(method, url, *, params=None, payload=None):
    for _ in range(6):
        response = requests.request(
            method,
            url,
            headers=NOTION_HEADERS,
            params=params,
            json=payload,
            timeout=45,
        )

        if response.status_code == 429:
            try:
                wait = float(response.headers.get("Retry-After", "1"))
            except ValueError:
                wait = 1.0
            time.sleep(wait)
            continue

        if response.status_code >= 400:
            raise RuntimeError(
                f"Notion API HTTP {response.status_code}: {response.text}"
            )

        return response.json() if response.text else {}

    raise RuntimeError("Notion API retries exhausted")


def existing_blocks():
    result = []
    cursor = None

    while True:
        params = {"page_size": 100}
        if cursor:
            params["start_cursor"] = cursor

        data = notion_request(
            "GET",
            f"https://api.notion.com/v1/blocks/{NOTION_PAGE_ID}/children",
            params=params,
        )
        result.extend(data.get("results", []))

        if not data.get("has_more"):
            break
        cursor = data.get("next_cursor")
        if not cursor:
            break

    return result


def text(content, url=None, bold=False):
    item = {
        "type": "text",
        "text": {"content": content},
        "annotations": {"bold": bold},
    }
    if url:
        item["text"]["link"] = {"url": url}
    return item


def notion_blocks(topics, raw_count, removed_count):
    now = datetime.now(LA_TZ).strftime("%Y-%m-%d %H:%M:%S")
    blocks = [
        {
            "object": "block",
            "type": "paragraph",
            "paragraph": {
                "rich_text": [
                    text(
                        f"最后更新：{now}（洛杉矶时间） | 抓取 {raw_count} 条 | "
                        f"保留 {len(topics)} 条 | 排除 {removed_count} 条",
                        bold=True,
                    )
                ]
            },
        },
        {"object": "block", "type": "divider", "divider": {}},
    ]

    current_date = None
    for index, topic in enumerate(topics, start=1):
        if topic["post_date"] != current_date:
            current_date = topic["post_date"]
            blocks.append({
                "object": "block",
                "type": "heading_2",
                "heading_2": {"rich_text": [text(current_date)]},
            })

        label = f"{index}. "
        if topic.get("display_time"):
            label += f"[{topic['display_time']}] "

        blocks.append({
            "object": "block",
            "type": "paragraph",
            "paragraph": {
                "rich_text": [
                    text(label),
                    text(topic["title"][:1800], url=topic["link"]),
                ]
            },
        })

    return blocks


def append_blocks(blocks):
    for start in range(0, len(blocks), 100):
        batch = blocks[start:start + 100]
        notion_request(
            "PATCH",
            f"https://api.notion.com/v1/blocks/{NOTION_PAGE_ID}/children",
            payload={"children": batch},
        )
        print(f"Notion wrote {min(start + 100, len(blocks))}/{len(blocks)} blocks")
        time.sleep(0.4)


def delete_blocks(blocks):
    for i, block in enumerate(blocks, start=1):
        block_id = block.get("id")
        if not block_id:
            continue
        notion_request(
            "DELETE",
            f"https://api.notion.com/v1/blocks/{block_id}",
        )
        time.sleep(0.36)
        if i % 25 == 0 or i == len(blocks):
            print(f"Deleted old blocks {i}/{len(blocks)}")


def replace_notion(topics, raw_count, removed_count):
    old = existing_blocks()
    new = notion_blocks(topics, raw_count, removed_count)

    # Write new content first. Only after success do we delete the old content.
    append_blocks(new)
    if old:
        delete_blocks(old)


def main():
    raw = scrape()
    kept, removed, reasons = filter_topics(raw)

    print("raw:", len(raw), "kept:", len(kept), "removed:", len(removed))
    for reason, count in reasons.most_common():
        print(f"  {reason}: {count}")

    save_csv("recent_all.csv", raw)
    save_csv("recent_kept.csv", kept)
    save_csv("recent_removed.csv", removed)

    replace_notion(kept, len(raw), len(removed))
    print("DONE")


if __name__ == "__main__":
    main()
