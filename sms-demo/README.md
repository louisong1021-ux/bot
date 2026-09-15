# SMS Demo — 最小版

现在只验证两个最核心功能：

1. `手机发短信 → Twilio → Python → OpenAI → Twilio → 手机收到 AI 回复`
2. `客户打电话 → 转到你的手机 → 没接 → 自动发短信 → 客户回复后由 AI 接待`

## 文件

- `app.py`：全部业务逻辑
- `requirements.txt`：Python 依赖
- `.env.example`：环境变量示例

## 1. 本地运行

```bash
cd sms-demo
python -m venv .venv
```

Windows：

```bash
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

填写 `.env`：

```env
OPENAI_API_KEY=...
OPENAI_MODEL=gpt-5.6-luna

TWILIO_ACCOUNT_SID=AC...
TWILIO_AUTH_TOKEN=...
TWILIO_PHONE_NUMBER=+1你的Twilio号码
FORWARD_TO_PHONE=+1你的真实手机号码
RING_TIMEOUT_SECONDS=20
```

`MISSED_CALL_TEXT` 可以不填；不填时会使用代码里的中英双语默认短信。

运行：

```bash
python app.py
```

健康检查：

```text
http://127.0.0.1:8000/health
```

## 2. 不接 Twilio 先测试 AI 短信回复

Windows PowerShell：

```powershell
curl.exe -X POST http://127.0.0.1:8000/sms -d "Body=你好，你们是做什么的？"
```

如果 OpenAI 正常，会返回一段 TwiML XML，其中 `<Message>` 里面就是 AI 回复。

## 3. 部署后配置 Twilio

假设公网地址是：

```text
https://example.com
```

Twilio 号码的 Messaging 设置：

```text
A message comes in
Webhook: https://example.com/sms
Method: POST
```

Twilio 号码的 Voice 设置：

```text
A call comes in
Webhook: https://example.com/voice
Method: POST
```

## 4. 漏接自动短信怎么工作

有人打 Twilio 号码时：

```text
客户来电
  ↓
POST /voice
  ↓
Twilio 把电话转到 FORWARD_TO_PHONE
  ↓
最多响 RING_TIMEOUT_SECONDS 秒
  ↓
如果接听：正常通话，不发短信
  ↓
如果 no-answer / busy / failed
  ↓
POST /dial-status
  ↓
Twilio REST API 自动给客户发一条短信
```

默认短信：

```text
Sorry we missed your call. 您好，刚才没能接到您的电话。Reply to this text and our AI assistant can help you now.
```

客户回复这条短信以后，Twilio 会把回复送到 `/sms`，然后 OpenAI 自动回答。

## 这一版故意没有做

- 不保存聊天记录
- 不记忆上一条短信
- 不同步 Notion
- 不识别 Lead
- 不做 CRM
- 不做数据库
- 不做 Twilio 签名校验
- 不做重复事件防重

这些等最小闭环真实跑通后再加。

## Demo 成功标准

只测试两件事：

1. 给 Twilio 号码发“你好” → 能收到 AI 回复。
2. 给 Twilio 号码打电话，故意不接 → 约 20 秒后收到自动短信；回复这条短信 → AI 能继续回答。

注意：Twilio Trial 账号通常只能向已验证的号码发送短信。真正用于美国商业短信时，还需要按 Twilio/运营商要求完成相应的号码和 A2P 10DLC 合规配置。
