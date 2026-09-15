import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv

load_dotenv()

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.responses import Response
from twilio.request_validator import RequestValidator
from twilio.twiml.messaging_response import MessagingResponse

import ai_agent
import db
from notion_sync import sync_lead_to_notion

STOP_WORDS = {"STOP", "STOPALL", "UNSUBSCRIBE", "CANCEL", "END", "QUIT"}
START_WORDS = {"START", "YES", "UNSTOP"}


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    yield


app = FastAPI(title="AI SMS Receptionist", version="0.1.0", lifespan=lifespan)


def twiml_reply(body):
    response = MessagingResponse()
    if body:
        response.message(body)
    return Response(content=str(response), media_type="application/xml")


def public_request_url(request: Request):
    base = os.getenv("PUBLIC_BASE_URL", "").strip().rstrip("/")
    if base:
        url = f"{base}{request.url.path}"
        if request.url.query:
            url += f"?{request.url.query}"
        return url
    return str(request.url)


async def validate_twilio(request: Request, form):
    auth_token = os.getenv("TWILIO_AUTH_TOKEN", "").strip()
    if not auth_token:
        if os.getenv("ALLOW_UNSIGNED_TWILIO", "false").lower() == "true":
            return
        raise HTTPException(status_code=500, detail="TWILIO_AUTH_TOKEN is not configured")

    signature = request.headers.get("X-Twilio-Signature", "")
    validator = RequestValidator(auth_token)
    if not validator.validate(public_request_url(request), dict(form), signature):
        raise HTTPException(status_code=403, detail="Invalid Twilio signature")


@app.get("/health")
def health():
    return {"ok": True, "service": "ai-sms-receptionist", "model": ai_agent.MODEL}


@app.post("/sms")
async def inbound_sms(request: Request, background_tasks: BackgroundTasks):
    form = await request.form()
    await validate_twilio(request, form)

    phone = (form.get("From") or "").strip()
    body = (form.get("Body") or "").strip()
    message_sid = (form.get("MessageSid") or "").strip()

    if not phone or not body:
        return twiml_reply("")

    cached = db.get_cached_reply(message_sid)
    if cached is not None:
        return twiml_reply(cached)

    normalized = body.upper().strip()
    if normalized in STOP_WORDS:
        db.set_opt_out(phone, True)
        reply = "You have been unsubscribed. Reply START to resume messages."
        db.cache_inbound(message_sid, phone, body, reply)
        return twiml_reply(reply)

    if normalized in START_WORDS:
        db.set_opt_out(phone, False)
        reply = "Messaging is active again. How can I help you?"
        db.cache_inbound(message_sid, phone, body, reply)
        return twiml_reply(reply)

    if db.is_opted_out(phone):
        db.cache_inbound(message_sid, phone, body, "")
        return twiml_reply("")

    db.cache_inbound(message_sid, phone, body)
    db.save_message(phone, "user", body)
    history = db.get_history(phone, limit=16)

    try:
        result = ai_agent.respond(history)
        reply = result["reply"]
    except Exception as exc:
        print(f"AI error for {phone}: {type(exc).__name__}: {exc}")
        reply = "Thanks for your message. I’m having a temporary issue right now. A team member can follow up shortly."
        result = {
            "human_handoff": True,
            "lead": {
                "is_lead": True,
                "name": None,
                "company": None,
                "industry": None,
                "need": body[:500],
                "preferred_callback": None,
                "summary": "AI reply failed; manual follow-up recommended.",
                "score": "warm",
            },
        }

    db.save_message(phone, "assistant", reply)
    db.cache_inbound(message_sid, phone, body, reply)

    lead = result.get("lead") or {}
    if lead.get("is_lead") or result.get("human_handoff"):
        db.upsert_lead(phone, lead, bool(result.get("human_handoff")))
        background_tasks.add_task(sync_lead_to_notion, phone)

    return twiml_reply(reply)


@app.post("/test-chat")
async def test_chat(request: Request, background_tasks: BackgroundTasks):
    if os.getenv("ENABLE_TEST_ENDPOINT", "false").lower() != "true":
        raise HTTPException(status_code=404, detail="Not found")

    payload = await request.json()
    phone = str(payload.get("phone") or "+15550000000")
    body = str(payload.get("body") or "").strip()
    if not body:
        raise HTTPException(status_code=400, detail="body is required")

    db.save_message(phone, "user", body)
    result = ai_agent.respond(db.get_history(phone, limit=16))
    db.save_message(phone, "assistant", result["reply"])

    lead = result.get("lead") or {}
    if lead.get("is_lead") or result.get("human_handoff"):
        db.upsert_lead(phone, lead, bool(result.get("human_handoff")))
        background_tasks.add_task(sync_lead_to_notion, phone)

    return result
