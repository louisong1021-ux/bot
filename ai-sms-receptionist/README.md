# AI SMS Receptionist

第一版自有 AI 短信客服后端：

`Twilio SMS → FastAPI webhook → OpenAI Responses API → SQLite conversation/lead state → optional Notion lead page`

## 已实现

- `POST /sms` 接收 Twilio 入站 SMS 并用 TwiML 回复
- OpenAI `gpt-5.6-luna` 默认模型，可用环境变量切换
- 自动跟随中英文
- SQLite 保存每个手机号的最近对话
- 单次 OpenAI 请求同时生成客户回复和 Lead 结构化数据
- 自动标记 `cold / warm / hot` Lead
- 用户要求报价、Demo、人工时自动标记 human handoff
- Twilio `MessageSid` 幂等缓存，Webhook 重试不会重复生成回复
- Twilio Webhook 签名校验
- STOP / START opt-out 基础处理
- 可选把 warm/hot Lead 创建成 Notion 子页面
- `/health` 健康检查
- 开发用 `/test-chat`，默认关闭

## 1. 本地启动

```bash
cd ai-sms-receptionist
python -m venv .venv
# Windows:
.venv\\Scripts\\activate
# macOS/Linux:
# source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env
```

填写至少：

```env
OPENAI_API_KEY=...
TWILIO_AUTH_TOKEN=...
PUBLIC_BASE_URL=https://你的公开地址
```

运行：

```bash
uvicorn app:app --reload --port 8000
```

访问 `http://127.0.0.1:8000/health` 应返回 `ok: true`。

## 2. 不接 Twilio 先测试 AI

在 `.env` 临时设置：

```env
ENABLE_TEST_ENDPOINT=true
```

然后：

```bash
curl -X POST http://127.0.0.1:8000/test-chat \
  -H "Content-Type: application/json" \
  -d '{"phone":"+16265550123","body":"我有一家装修公司，经常漏接客户电话"}'
```

测试完成后把 `ENABLE_TEST_ENDPOINT=false`。

## 3. 接 Twilio

Twilio 号码控制台 → Messaging → **A message comes in**：

- Webhook: `https://你的域名/sms`
- Method: `POST`

Twilio 对入站短信会同步调用这个 Webhook，并期待 TwiML 响应。生产环境必须配置 `TWILIO_AUTH_TOKEN` 并保持 `ALLOW_UNSIGNED_TWILIO=false`。

如果部署在反向代理/Cloudflare/Render 后面，`PUBLIC_BASE_URL` 必须填写 Twilio 实际访问的外部 HTTPS 根地址，否则签名验证可能因为 URL 不一致而失败。

## 4. Notion（可选）

不要指向招聘帖子页面。新建一个专门保存销售线索的 Notion 页面，把 integration 分享给这个页面，再设置：

```env
NOTION_TOKEN=ntn_...
NOTION_PARENT_PAGE_ID=...
```

warm/hot Lead 会作为该页面的子页面创建。没有这两个变量时，短信客服照常运行，只是不写 Notion。

## 5. 生产注意事项

- OpenAI API key、Twilio Auth Token、Notion Token 只能放服务器环境变量，不能放 GitHub Pages 前端。
- 第一版只做 **客户主动发短信 → AI 回复**，暂时不做营销群发。
- 真正给美国客户商业发送 A2P SMS 前，需要按 Twilio/运营商要求完成相应的 A2P 10DLC/合规配置。
- Twilio 入站 Webhook 是同步请求，因此 AI 请求设置了短超时；后续可以升级为队列/异步发送架构以提高稳定性。

## 下一步

1. 部署到一个有固定 HTTPS 地址的服务器。
2. 把 Twilio 号码的入站 Messaging Webhook 指向 `/sms`。
3. 用真实手机给 Demo 号码发短信测试。
4. 再增加“漏接电话 → 自动发短信”流程。
