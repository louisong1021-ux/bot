import html
import json
import re
import types
from urllib.parse import urljoin

import requests

import main

MD_LINK = re.compile(r"\[([^\]]+)\]\((https?://[^)]+)\)")


def _alt_domain(url: str):
    if "www.chineseinla.com" in url:
        return url.replace("www.chineseinla.com", "www.chineseinla.cn")
    if "chineseinla.com" in url:
        return url.replace("chineseinla.com", "chineseinla.cn")
    return None


def _direct(url: str):
    r = main.session.get(url, timeout=30, allow_redirects=True)
    r.raise_for_status()
    if not r.encoding or r.encoding.lower() == "iso-8859-1":
        r.encoding = r.apparent_encoding
    return r


def _jina(target_url: str):
    r = requests.get(
        "https://r.jina.ai/" + target_url,
        headers={
            "Accept": "application/json",
            "X-Retain-Links": "all",
            "X-No-Cache": "true",
            "X-Timeout": "30",
        },
        timeout=60,
    )
    r.raise_for_status()

    content = ""
    try:
        data = r.json()
        if isinstance(data, dict):
            if isinstance(data.get("data"), dict):
                content = data["data"].get("content", "") or ""
            content = content or data.get("content", "") or ""
    except (ValueError, json.JSONDecodeError):
        content = r.text

    return content


def _markdown_to_synthetic_html(markdown: str, base_url: str):
    lines = markdown.splitlines()
    topic_rows = []
    forum_links = []
    seen_topics = set()

    for i, line in enumerate(lines):
        for match in MD_LINK.finditer(line):
            label = match.group(1).strip()
            href = match.group(2).strip()

            if "page_viewtopic" in href:
                if href in seen_topics:
                    continue
                seen_topics.add(href)
                context = " ".join(lines[max(0, i - 2): min(len(lines), i + 6)])
                topic_rows.append(
                    "<tr><td>"
                    f'<a href="{html.escape(href, quote=True)}">{html.escape(label)}</a> '
                    f"{html.escape(context)}"
                    "</td></tr>"
                )

            elif "page_viewforum" in href:
                forum_links.append(
                    f'<a href="{html.escape(href, quote=True)}">{html.escape(label)}</a>'
                )

    return "<html><body><table>" + "".join(topic_rows) + "</table>" + "".join(forum_links) + "</body></html>"


def github_safe_get_page(url: str):
    candidates = [url]
    alt = _alt_domain(url)
    if alt:
        candidates.append(alt)

    diagnostics = []

    for candidate in candidates:
        try:
            r = _direct(candidate)
            body = r.text or ""
            diagnostics.append(
                f"direct {candidate} status={r.status_code} chars={len(body)}"
            )
            if "page_viewtopic" in body:
                print(diagnostics[-1])
                return r
        except Exception as exc:
            diagnostics.append(
                f"direct {candidate} error={type(exc).__name__}: {exc}"
            )

    for candidate in candidates:
        try:
            markdown = _jina(candidate)
            diagnostics.append(f"jina {candidate} chars={len(markdown)}")
            if "page_viewtopic" in markdown:
                print(diagnostics[-1])
                synthetic = _markdown_to_synthetic_html(markdown, candidate)
                return types.SimpleNamespace(text=synthetic, status_code=200, url=candidate)
        except Exception as exc:
            diagnostics.append(
                f"jina {candidate} error={type(exc).__name__}: {exc}"
            )

    main.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (main.OUTPUT_DIR / "debug_fetch.txt").write_text(
        "\n".join(diagnostics), encoding="utf-8"
    )
    raise RuntimeError(
        "ChineseInLA returned no usable topic content.\n" + "\n".join(diagnostics)
    )


main.get_page = github_safe_get_page

if __name__ == "__main__":
    main.main()
