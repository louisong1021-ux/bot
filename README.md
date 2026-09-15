# bot

脚本仓库。

## ChineseInLA → Notion

项目目录：`chineseinla-notion/`

- `chineseinla-notion/main.py`：抓取、筛选和 Notion 同步逻辑
- `chineseinla-notion/runner.py`：运行入口与重试逻辑
- `chineseinla-notion/requirements.txt`：依赖
- `chineseinla-notion/README.md`：项目说明

GitHub Actions 配置在 `.github/workflows/`。生产任务 `chineseinla-notion.yml` 每 2 小时运行一次，也可以手动触发。

仓库约定：`bot` 用于脚本和定期执行任务；可公开访问的网页放在 `cslb`。
