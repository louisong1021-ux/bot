# bot

脚本和后端自动化仓库。

## ChineseInLA → Notion

项目目录：`chineseinla-notion/`

- `chineseinla-notion/main.py`：抓取、筛选和 Notion 同步逻辑
- `chineseinla-notion/runner.py`：运行入口与重试逻辑
- `chineseinla-notion/requirements.txt`：依赖
- `chineseinla-notion/README.md`：项目说明

GitHub Actions 配置在 `.github/workflows/`。生产任务 `chineseinla-notion.yml` 每 2 小时运行一次，也可以手动触发。

## AI SMS Receptionist

项目目录：`ai-sms-receptionist/`

第一版流程：`Twilio SMS → FastAPI → OpenAI → SQLite → optional Notion`。

- `app.py`：Twilio SMS Webhook 和测试接口
- `ai_agent.py`：OpenAI Responses API 客服逻辑与 Lead 结构化输出
- `db.py`：对话、Lead、幂等和 opt-out 状态
- `notion_sync.py`：可选 Notion Lead 同步
- `Dockerfile`：部署入口
- `README.md`：本地测试和 Twilio 配置说明

仓库约定：`bot` 用于脚本、自动化和后端服务；可公开访问的静态网页放在 `cslb`。
