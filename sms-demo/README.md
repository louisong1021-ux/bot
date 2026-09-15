# SMS Demo — 最小版

目标只有一个：

`手机发短信 → Twilio → Python → OpenAI → Twilio → 手机收到 AI 回复`

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

把 `.env` 中的 `OPENAI_API_KEY` 改成自己的 API Key，然后运行：

```bash
python app.py
```

健康检查：

```text
http://127.0.0.1:8000/health
```

## 2. 不接 Twilio 先测试

Windows PowerShell：

```powershell
curl.exe -X POST http://127.0.0.1:8000/sms -d "Body=你好，你们是做什么的？"
```

如果 OpenAI 正常，会返回一段 TwiML XML，其中 `<Message>` 里面就是 AI 回复。

## 3. 接 Twilio

把这个程序部署到一个公网 HTTPS 地址，例如：

```text
https://example.com/sms
```

然后在 Twilio 电话号码的 Messaging 设置里，把 **A message comes in** 设置为：

```text
Webhook: https://example.com/sms
Method: POST
```

之后用手机给这个 Twilio 号码发短信即可。

## 这一版故意没有做

- 不保存聊天记录
- 不记忆上一条短信
- 不同步 Notion
- 不识别 Lead
- 不做 CRM
- 不做数据库
- 不做漏接电话自动短信
- 不做 Twilio 签名校验

这些等“真实短信 → AI → 真实回复”跑通后，再一个一个加。
