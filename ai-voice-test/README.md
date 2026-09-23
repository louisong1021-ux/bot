# ai-voice-test

Single-number minimal AI phone demo.

Target architecture:

`Twilio ConversationRelay -> Cloudflare Worker -> Durable Object -> OpenAI`

## Scope

First version only:

- one Twilio phone number
- Chinese and English conversation
- collect name, city, need, budget, and timeline
- multi-turn context
- generate a text summary on hangup
- print the first summary to Cloudflare Logs
- no database
- no SMS
- no human transfer
- no multi-customer product layer

## Development order

- [x] A. Worker skeleton + `GET /health`
- [ ] B. Durable Object + WebSocket
- [ ] C. OpenAI streaming
- [ ] D. Twilio ConversationRelay
- [ ] E. Hangup summary

Each stage must pass its tests before the next stage begins.

## Stage A

`GET /health` returns:

```json
{
  "ok": true,
  "service": "ai-voice-test",
  "stage": "A"
}
```

Unknown routes return HTTP 404.

### Local commands

```bash
npm install
npm test
npm run typecheck
npm run dev
```

### Deployment

```bash
npm run deploy
```

Deployment requires Cloudflare authorization. Do not put API keys or other secrets in source control.

## Secrets

Never commit secrets.

Local-only files such as `.dev.vars`, `.env`, and `.env.*` are ignored. Production secrets will be configured with Cloudflare secrets / environment bindings.
