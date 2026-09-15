import os
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import requests

NOTION_TOKEN = os.environ.get("NOTION_TOKEN", "").strip()
NOTION_PAGE_ID = "3dbc18c6fba48086a663f8fe7d77a9a3"
NOTION_VERSION = "2022-06-28"
LA_TZ = ZoneInfo("America/Los_Angeles")

if not NOTION_TOKEN:
    raise RuntimeError("Missing GitHub Actions secret: NOTION_TOKEN")

headers = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": NOTION_VERSION,
    "Content-Type": "application/json",
}


def notion_request(method, url, *, params=None, json=None):
    response = requests.request(
        method,
        url,
        headers=headers,
        params=params,
        json=json,
        timeout=45,
    )

    print(method, url, "HTTP:", response.status_code)

    if response.status_code >= 400:
        raise RuntimeError(
            f"Notion API failed: HTTP {response.status_code}: {response.text}"
        )

    if response.text:
        return response.json()

    return {}


def get_existing_top_level_blocks():
    blocks = []
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

        blocks.extend(data.get("results", []))

        if not data.get("has_more"):
            break

        cursor = data.get("next_cursor")
        if not cursor:
            break

    return blocks


def make_new_blocks():
    now = datetime.now(LA_TZ).strftime("%Y-%m-%d %H:%M:%S")

    fixed_lines = [
        "覆盖测试成功：这是新页面内容",
        "测试 1：旧内容应该已经全部被替换",
        "测试 2：本次测试不访问 ChineseInLA",
        "测试 3：GitHub Actions → Python → Notion 正常",
        "测试 4：以后爬虫结果也可以用同样方式整页覆盖",
        f"覆盖时间：{now}（洛杉矶时间）",
    ]

    children = []

    for index, line in enumerate(fixed_lines):
        block_type = "heading_1" if index == 0 else "paragraph"
        children.append({
            "object": "block",
            "type": block_type,
            block_type: {
                "rich_text": [
                    {
                        "type": "text",
                        "text": {"content": line},
                    }
                ]
            },
        })

    return children


def append_new_content(children):
    notion_request(
        "PATCH",
        f"https://api.notion.com/v1/blocks/{NOTION_PAGE_ID}/children",
        json={"children": children},
    )


def delete_old_blocks(old_blocks):
    total = len(old_blocks)
    deleted = 0
    skipped = 0

    for index, block in enumerate(old_blocks, start=1):
        block_id = block.get("id")

        if not block_id:
            skipped += 1
            continue

        if block.get("archived") or block.get("in_trash"):
            skipped += 1
            continue

        response = requests.delete(
            f"https://api.notion.com/v1/blocks/{block_id}",
            headers=headers,
            timeout=45,
        )

        if response.status_code == 429:
            wait_seconds = float(response.headers.get("Retry-After", "1"))
            time.sleep(wait_seconds)
            response = requests.delete(
                f"https://api.notion.com/v1/blocks/{block_id}",
                headers=headers,
                timeout=45,
            )

        if response.status_code >= 400:
            text = response.text.lower()
            if "archived" in text or "in_trash" in text:
                skipped += 1
                continue
            raise RuntimeError(
                f"Delete old block failed: HTTP {response.status_code}: {response.text}"
            )

        deleted += 1
        time.sleep(0.36)

        if index % 50 == 0 or index == total:
            print(
                f"old blocks processed: {index}/{total}, "
                f"deleted={deleted}, skipped={skipped}"
            )

    print(f"cleanup complete: deleted={deleted}, skipped={skipped}")


def main():
    # 1. 先记录当前页面所有旧 block。
    old_blocks = get_existing_top_level_blocks()
    print("existing top-level blocks:", len(old_blocks))

    # 2. 先把新内容写进去。
    #    如果这一步失败，旧内容完全不动。
    new_blocks = make_new_blocks()
    append_new_content(new_blocks)
    print("new fixed content written:", len(new_blocks))

    # 3. 只删除第 1 步记录下来的旧 block。
    #    新写入的 block 不在 old_blocks 里，因此不会被删。
    delete_old_blocks(old_blocks)

    print("FULL_REPLACE_TEST_SUCCESS")


if __name__ == "__main__":
    main()
