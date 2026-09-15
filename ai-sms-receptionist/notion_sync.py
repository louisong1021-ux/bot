import os
from datetime import datetime, timezone

import requests

from db import get_lead, mark_notion_page

NOTION_VERSION = "2022-06-28"


def _text(content, bold=False):
    return {
        "type": "text",
        "text": {"content": str(content)},
        "annotations": {"bold": bold}
    }


def sync_lead_to_notion(phone):
    token = os.getenv("NOTION_TOKEN", "").strip()
    parent_page_id = os.getenv("NOTION_PARENT_PAGE_ID", "").strip()
    if not token or not parent_page_id:
        return

    lead = get_lead(phone)
    if not lead or lead.get("notion_page_id"):
        return
    if lead.get("score") not in {"warm", "hot"} and not lead.get("human_handoff"):
        return

    title_bits = [lead.get("company"), lead.get("name"), phone]
    title = " · ".join(bit for bit in title_bits if bit)[:180]

    lines = [
        ("Phone", phone),
        ("Name", lead.get("name")),
        ("Company", lead.get("company")),
        ("Industry", lead.get("industry")),
        ("Need", lead.get("need")),
        ("Preferred callback", lead.get("preferred_callback")),
        ("Lead score", lead.get("score")),
        ("Human handoff", "Yes" if lead.get("human_handoff") else "No"),
        ("Summary", lead.get("summary")),
        ("Captured at", datetime.now(timezone.utc).isoformat())
    ]

    children = []
    for label, value in lines:
        if value in (None, ""):
            continue
        children.append({
            "object": "block",
            "type": "paragraph",
            "paragraph": {
                "rich_text": [_text(f"{label}: ", bold=True), _text(value)]
            }
        })

    response = requests.post(
        "https://api.notion.com/v1/pages",
        headers={
            "Authorization": f"Bearer {token}",
            "Notion-Version": NOTION_VERSION,
            "Content-Type": "application/json"
        },
        json={
            "parent": {"type": "page_id", "page_id": parent_page_id},
            "properties": {
                "title": {
                    "type": "title",
                    "title": [_text(title)]
                }
            },
            "children": children
        },
        timeout=12
    )
    response.raise_for_status()
    page_id = response.json().get("id")
    if page_id:
        mark_notion_page(phone, page_id)
