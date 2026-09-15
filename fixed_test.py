import os
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

now = datetime.now(LA_TZ).strftime("%Y-%m-%d %H:%M:%S")

fixed_lines = [
    "固定内容测试：GitHub Actions → Notion",
    "测试 1：GitHub Actions 可以运行 Python",
    "测试 2：NOTION_TOKEN Secret 可以被读取",
    "测试 3：Notion API 可以正常写入页面",
    "测试 4：本次测试完全不访问 ChineseInLA，也不运行爬虫",
    f"测试时间：{now}（洛杉矶时间）",
]

children = []
for index, line in enumerate(fixed_lines):
    block_type = "heading_2" if index == 0 else "paragraph"
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

url = f"https://api.notion.com/v1/blocks/{NOTION_PAGE_ID}/children"
response = requests.patch(url, headers=headers, json={"children": children}, timeout=45)

print("HTTP:", response.status_code)
print(response.text)

if response.status_code != 200:
    raise RuntimeError(f"Notion write failed: HTTP {response.status_code}")

print("FIXED_CONTENT_TEST_SUCCESS")
