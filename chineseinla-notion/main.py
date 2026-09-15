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
START_URL = "https://www.chineseinla.com/f/page_viewforum/f_29.html"
MAX_PAGES = 100
STOP_AFTER_OLD_PAGES = 2
MIN_OLD_ROWS_FOR_STOP = 5
MIN_OLD_RATIO_FOR_STOP = 0.50
REQUEST_DELAY_SECONDS = 0.8

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
# These always stay even if another keyword would otherwise match a remove rule.
FORCE_KEEP_KEYWORDS = [
    "幼儿园", "幼稚园", "preschool", "daycare", "学校前台",
    "设备维保", "设备维护", "设备维修", "机修", "维修技师",
    "maintenance technician", "maintenance mechanic",
]

REMOVE_RULES = {
    "个人求职": [
        "本人找工作", "本人求工作", "本人求职", "寻找工作", "寻工作",
        "求兼职", "求全职", "求一份工作", "找工作求职",
    ],
    "保险/理财": [
        "保险", "insurance agent", "insurance broker", "insurance advisor",
        "保险经纪", "保险代理", "兼职写单", "写单人员", "理财顾问",
        "financial advisor", "financial consultant",
    ],
    "Uber/大黑/Lyft": [
        "uber", "lyft", "大黑", "网约车司机", "rideshare",
    ],
    "牙科/医疗/医美": [
        "牙科", "牙医", "dental assistant", "dental receptionist",
        "dental office", "护士", "护理员", "护理人员", "lvn", "cna",
        "medical assistant", "医疗助理", "诊所前台", "medical office",
        "nursing facility", "医美", "medical spa", "med spa",
    ],
    "按摩/美容/SPA": [
        "按摩", "massage", "spa", "美容", "美甲", "nail salon",
    ],
    "律师/律所": [
        "律师", "律所", "law firm", "attorney", "legal assistant",
    ],
    "培训/办证/招生": [
        "包教包会包就业", "包教包会", "包就业", "培训班", "考试培训",
        "考证培训", "招生", "帮办执照", "快速下证", "资格培训",
    ],
    "个人接活/服务广告": [
        "本人接活", "个人接活", "承接装修", "装修服务", "搬家服务",
        "上门维修", "可上门", "接各种", "承接各类", "家庭小维修",
    ],
    "车主/加盟/合伙": [
        "车主加盟", "码头车主", "招车主", "找车主", "车主合作",
        "合伙人", "招合伙", "加盟", "承包路线",
    ],
    "明显营销/引流": [
        "轻松月入", "零基础创业", "免费创业", "高收入副业",
        "被动收入", "财富自由", "加微信了解", "私信了解",
        "做学生利益的守护者",
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
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
})

TIME_PATTERN = re.compile(
    r"\b(?P<hour>1[0-2]|0?[1-9]):(?P<minute>[0-5][0-9])\s*(?P<ampm>am|pm)\b",
    re.IGNORECASE,
)

# ChineseInLA topic rows normally end with:
#   ... author 7:30 am 0 123
# or
#   ... author 2026-09-14 0 123
# Restricting parsing to the row tail prevents unrelated times/dates in titles/body text
# from being mistaken for the refresh timestamp.
ROW_TIME_PATTERN = re.compile(
    r"(?P<time>(?:1[0-2]|0?[1-9]):[0-5][0-9]\s*(?:am|pm))"
    r"(?:\s+\d+){0,3}\s*$",
    re.IGNORECASE,
)
ROW_DATE_PATTERN = re.compile(
    r"(?P<date>20\d{2}-\d{2}-\d{2})(?:\s+\d+){0,3}\s*$"
)


def clean_text(text):
    if not text:
        return ""
    return re.sub(r"\s+", " ", text.replace("\u00a0", " ")).strip()


def target_date():
    return datetime.now(LA_TZ).date()


def parse_time_24(value):
    match = TIME_PATTERN.search(value)
    if not match:
        return None

    hour = int(match.group("hour"))
    minute = int(match.group("minute"))
    am_pm = match.group("ampm").lower()

    if am_pm == "am":
        hour_24 = 0 if hour == 12 else hour
    else:
        hour_24 = 12 if hour == 12 else hour + 12

    return f"{hour_24:02d}:{minute:02d}"


def extract_refresh_info(context, run_date):
    """Classify a topic row as today, dated history, or unknown."""
    context = clean_text(context)

    time_match = ROW_TIME_PATTERN.search(context)
    if time_match:
        original = clean_text(time_match.group("time"))
        time_24 = parse_time_24(original)
        if time_24:
            return {
                "kind": "today",
                "post_date": run_date.isoformat(),
                "display_time": original,
                "time_24": time_24,
                "parsed_date": run_date,
            }

    date_match = ROW_DATE_PATTERN.search(context)
    if date_match:
        date_string = date_match.group("date")
        try:
            parsed = datetime.strptime(date_string, "%Y-%m-%d").date()
        except ValueError:
            parsed = None

        if parsed:
            return {
                "kind": "date",
                "post_date": parsed.isoformat(),
                "display_time": "",
                "time_24": "00:00",
                "parsed_date": parsed,
            }

    return {
        "kind": "unknown",
        "post_date": "",
        "display_time": "",
        "time_24": "",
        "parsed_date": None,
    }


def get_page(url):
    response = session.get(url, timeout=30, allow_redirects=True)
    response.raise_for_status()

    if not response.encoding or response.encoding.lower() == "iso-8859-1":
        response.encoding = response.apparent_encoding

    return response


def topic_context(anchor):
    """Get only the closest topic row when possible, avoiding whole-page contamination."""
    topic_row = anchor.find_parent("div", class_="topic_list_detail")
    if topic_row:
        return clean_text(topic_row.get_text(" ", strip=True))

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

    for anchor in soup.select('a[href*="page_viewforum"]'):
        text = clean_text(anchor.get_text(" ", strip=True))
        href = anchor.get("href", "")
        if not href:
            continue

        links.append((text, urljoin(current_url, href)))

    # First preference: explicit next-page UI.
    for text, href in links:
        if (
            "下一页" in text
            or "next" in text.lower()
            or text in [">", "›", "»", "→"]
        ) and href != current_url:
            return href

    # Fallback: choose the smallest start_N larger than the current page.
    current = start_number(current_url)
    if current is None:
        current = 0

    candidates = []
    for _, href in links:
        value = start_number(href)
        if value is not None and value > current:
            candidates.append((value, href))

    if not candidates:
        return None

    candidates.sort(key=lambda item: item[0])
    return candidates[0][1]


def classify(topic):
    text = clean_text(
        f"{topic.get('title', '')} {topic.get('context', '')}"
    ).lower()

    for keyword in FORCE_KEEP_KEYWORDS:
        if keyword.lower() in text:
            return True, "强制保留"

    for reason, keywords in REMOVE_RULES.items():
        for keyword in keywords:
            if keyword.lower() in text:
                return False, reason

    # When a title is too short to classify safely, keep it rather than deleting it.
    # This follows the prior workflow's "待核对，不误删" rule.
    if len(clean_text(topic.get("title", ""))) <= 3:
        return True, "待核对"

    return True, "保留"


def scrape():
    run_date = target_date()
    yesterday = run_date - timedelta(days=1)

    print()
    print("=" * 72)
    print("ChineseInLA 工作求职 - requests 安全爬虫版")
    print("本次目标日期：", run_date.isoformat())
    print("=" * 72)

    current_url = START_URL
    page_number = 1

    seen_topic_links = set()
    seen_unknown_links = set()
    today_topics = []

    consecutive_old_pages = 0
    visited_pages = set()

    while page_number <= MAX_PAGES:
        # Do not mix two calendar days if a run crosses midnight in Los Angeles.
        if target_date() != run_date:
            raise RuntimeError(
                "洛杉矶日期在本次运行中发生变化，为避免混入两个自然日，本次停止写入。"
            )

        if current_url in visited_pages:
            print("检测到分页循环，停止。")
            break
        visited_pages.add(current_url)

        print()
        print("=" * 72)
        print(f"第 {page_number} 页")
        print(current_url)
        print("=" * 72)

        response = get_page(current_url)
        print("HTTP：", response.status_code)

        soup = BeautifulSoup(response.text, "html.parser")
        anchors = soup.select('a[href*="page_viewtopic"]')
        print("检测到帖子链接：", len(anchors))

        if not anchors:
            OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            debug_file = OUTPUT_DIR / "debug_no_topics.html"
            debug_file.write_text(response.text, encoding="utf-8")
            raise RuntimeError(
                "页面访问成功，但没有解析到任何帖子链接。"
                f" 已保存调试页面：{debug_file}"
            )

        page_seen = set()
        page_topics = []

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
            refresh = extract_refresh_info(context, run_date)

            page_topics.append({
                "page": page_number,
                "title": title,
                "context": context,
                "link": href,
                "page_url": current_url,
                "refresh_kind": refresh["kind"],
                "post_date": refresh["post_date"],
                "display_time": refresh["display_time"],
                "time_24": refresh["time_24"],
                "parsed_date": refresh["parsed_date"],
            })

        page_today = [
            topic for topic in page_topics
            if topic["refresh_kind"] == "today"
        ]
        page_dated = [
            topic for topic in page_topics
            if topic["refresh_kind"] == "date"
        ]
        page_unknown = [
            topic for topic in page_topics
            if topic["refresh_kind"] == "unknown"
        ]

        old_topics = [
            topic for topic in page_dated
            if topic["parsed_date"] and topic["parsed_date"] <= yesterday
        ]

        new_unknown = []
        for topic in page_unknown:
            if topic["link"] not in seen_unknown_links:
                seen_unknown_links.add(topic["link"])
                new_unknown.append(topic)

        for topic in page_today:
            if topic["link"] in seen_topic_links:
                continue
            seen_topic_links.add(topic["link"])
            today_topics.append(topic)

        # Also mark non-today links as seen so sticky/pinned repeats are not treated as new.
        for topic in page_topics:
            seen_topic_links.add(topic["link"])

        print()
        print("本页不同帖子：", len(page_topics))
        print("本页今天刷新：", len(page_today))
        print("本页日期格式：", len(page_dated))
        print("本页无法识别时间：", len(page_unknown))
        print("本页新出现未知帖：", len(new_unknown))
        print("目前今天去重总数：", len(today_topics))

        if new_unknown:
            print()
            print("⚠ 本页存在首次出现、无法识别刷新时间的帖子：")
            for topic in new_unknown[:10]:
                print("  -", topic["title"])

        for index, topic in enumerate(page_today[:5], start=1):
            print(
                f"{index}. [{topic['display_time']}] "
                f"{topic['title']}"
            )

        old_ratio = (
            len(old_topics) / len(page_topics)
            if page_topics else 0.0
        )
        all_dated_are_old = (
            bool(page_dated)
            and all(
                topic["parsed_date"] is not None
                and topic["parsed_date"] <= yesterday
                for topic in page_dated
            )
        )

        safe_old_page = (
            len(page_today) == 0
            and len(old_topics) >= MIN_OLD_ROWS_FOR_STOP
            and old_ratio >= MIN_OLD_RATIO_FOR_STOP
            and all_dated_are_old
            and len(new_unknown) == 0
        )

        if safe_old_page:
            consecutive_old_pages += 1
            print(
                "已确认当前页以旧帖为主："
                f"old={len(old_topics)}, ratio={old_ratio:.0%}, "
                f"连续确认={consecutive_old_pages}/{STOP_AFTER_OLD_PAGES}"
            )
        else:
            consecutive_old_pages = 0

        if consecutive_old_pages >= STOP_AFTER_OLD_PAGES:
            print("连续两页已安全确认进入旧帖区域，停止。")
            break

        nxt = next_page(soup, current_url)
        if not nxt:
            print("没有找到下一页，停止。")
            break

        if nxt == current_url:
            print("下一页与当前页相同，停止。")
            break

        current_url = nxt
        page_number += 1
        time.sleep(REQUEST_DELAY_SECONDS)

    if target_date() != run_date:
        raise RuntimeError(
            "洛杉矶日期在本次运行结束前发生变化，本次停止写入。"
        )

    if not today_topics:
        raise RuntimeError(
            "没有识别到今天刷新帖。为避免误清空 Notion，本次停止写入。"
        )

    today_topics.sort(
        key=lambda topic: topic.get("time_24", ""),
        reverse=True,
    )

    print()
    print("=" * 72)
    print("爬取完成")
    print("今天去重帖子：", len(today_topics))
    print("=" * 72)

    return today_topics


def filter_topics(topics):
    kept = []
    removed = []
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
        "post_date",
        "display_time",
        "page",
        "title",
        "link",
        "filter_reason",
        "context",
    ]

    with open(
        OUTPUT_DIR / name,
        "w",
        newline="",
        encoding="utf-8-sig",
    ) as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()

        for topic in topics:
            writer.writerow({
                field: topic.get(field, "")
                for field in fields
            })


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
    run_date = target_date().isoformat()

    blocks = [
        {
            "object": "block",
            "type": "paragraph",
            "paragraph": {
                "rich_text": [
                    text(
                        f"最后更新：{now}（洛杉矶时间） | "
                        f"今天抓取 {raw_count} 条 | "
                        f"保留 {len(topics)} 条 | 排除 {removed_count} 条",
                        bold=True,
                    )
                ]
            },
        },
        {"object": "block", "type": "divider", "divider": {}},
        {
            "object": "block",
            "type": "heading_2",
            "heading_2": {"rich_text": [text(run_date)]},
        },
    ]

    for index, topic in enumerate(topics, start=1):
        label = f"{index}. "
        if topic.get("display_time"):
            label += f"[{topic['display_time']}] "

        note = ""
        if topic.get("filter_reason") == "待核对":
            note = " 〔待核对〕"

        blocks.append({
            "object": "block",
            "type": "paragraph",
            "paragraph": {
                "rich_text": [
                    text(label),
                    text(topic["title"][:1750], url=topic["link"]),
                    text(note),
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

        print(
            f"Notion wrote "
            f"{min(start + 100, len(blocks))}/{len(blocks)} blocks"
        )
        time.sleep(0.4)


def delete_blocks(blocks):
    for index, block in enumerate(blocks, start=1):
        block_id = block.get("id")
        if not block_id:
            continue

        if block.get("archived") or block.get("in_trash"):
            continue

        notion_request(
            "DELETE",
            f"https://api.notion.com/v1/blocks/{block_id}",
        )

        time.sleep(0.36)

        if index % 25 == 0 or index == len(blocks):
            print(f"Deleted old blocks {index}/{len(blocks)}")


def replace_notion(topics, raw_count, removed_count):
    old = existing_blocks()
    new = notion_blocks(topics, raw_count, removed_count)

    # Write new content first. Only delete the previous snapshot after the new
    # snapshot has been written successfully.
    append_blocks(new)

    if old:
        delete_blocks(old)


def main():
    raw = scrape()
    kept, removed, reasons = filter_topics(raw)

    print()
    print(
        "raw:", len(raw),
        "kept:", len(kept),
        "removed:", len(removed),
    )

    for reason, count in reasons.most_common():
        print(f"  {reason}: {count}")

    save_csv("today_all.csv", raw)
    save_csv("today_kept.csv", kept)
    save_csv("today_removed.csv", removed)

    replace_notion(
        kept,
        raw_count=len(raw),
        removed_count=len(removed),
    )

    print("DONE")


if __name__ == "__main__":
    main()
