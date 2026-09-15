import time

import main


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


# Only patch Notion cleanup. All ChineseInLA fetching remains exactly in
# main.py and uses the fixed www.chineseinla.com URL.
main.delete_blocks = safe_delete_blocks


if __name__ == "__main__":
    main.main()
