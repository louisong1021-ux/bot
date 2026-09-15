import time

import main


def reset_http_session():
    """Start a fresh HTTP session while keeping the same request headers."""
    old_headers = dict(main.session.headers)
    try:
        main.session.close()
    except Exception:
        pass

    main.session = main.requests.Session()
    main.session.headers.update(old_headers)


def resilient_scrape():
    """Retry transient failures from the same fixed ChineseInLA URL only."""
    attempts = 4

    for attempt in range(1, attempts + 1):
        try:
            return original_scrape()
        except main.requests.RequestException as exc:
            retryable = True
            error = exc
        except RuntimeError as exc:
            message = str(exc).lower()
            retryable = (
                "no topic links were parsed" in message
                or "没有解析到任何帖子链接" in message
                or "页面访问成功，但没有解析到任何帖子链接" in message
            )
            error = exc

        if not retryable or attempt == attempts:
            raise error

        wait_seconds = attempt * 5
        print(
            f"ChineseInLA attempt {attempt}/{attempts} failed: {error}. "
            f"Retrying the same fixed URL in {wait_seconds}s..."
        )
        reset_http_session()
        time.sleep(wait_seconds)

    raise RuntimeError("ChineseInLA retries exhausted")


def safe_delete_blocks(blocks):
    """Delete old Notion blocks idempotently.

    A previous failed run may already have archived some blocks. Notion returns
    HTTP 400 if DELETE is called on an already archived block, so those blocks
    are skipped instead of failing the whole sync.
    """
    total = len(blocks)
    deleted = 0
    skipped = 0

    for index, block in enumerate(blocks, start=1):
        block_id = block.get("id")

        if not block_id:
            skipped += 1
            continue

        if block.get("archived") or block.get("in_trash"):
            skipped += 1
            continue

        try:
            main.notion_request(
                "DELETE",
                f"https://api.notion.com/v1/blocks/{block_id}",
            )
            deleted += 1
        except RuntimeError as exc:
            message = str(exc).lower()
            if "archived" in message or "in_trash" in message:
                skipped += 1
                continue
            raise

        time.sleep(0.36)

        if index % 20 == 0 or index == total:
            print(
                f"old blocks: {index}/{total} "
                f"deleted={deleted} skipped={skipped}"
            )

    print(f"old block cleanup complete: deleted={deleted}, skipped={skipped}")


# Keep all ChineseInLA fetching in main.py and on the fixed www.chineseinla.com
# source. This wrapper only retries the same source when GitHub receives a
# transient empty/failed response.
original_scrape = main.scrape
main.scrape = resilient_scrape

# Make Notion cleanup safe to repeat after a partially completed run.
main.delete_blocks = safe_delete_blocks


if __name__ == "__main__":
    main.main()
