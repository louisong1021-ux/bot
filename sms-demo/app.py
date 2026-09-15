import os

from dotenv import load_dotenv
from flask import Flask, Response, request
from openai import OpenAI
from twilio.rest import Client
from twilio.twiml.messaging_response import MessagingResponse
from twilio.twiml.voice_response import VoiceResponse

load_dotenv()

app = Flask(__name__)
MODEL = os.getenv("OPENAI_MODEL", "gpt-5.6-luna")

INSTRUCTIONS = (
    "You are a concise bilingual SMS receptionist for an AI customer-service company. "
    "Reply in the user's language. Keep replies to 1-3 short sentences. "
    "Be helpful and natural. Do not invent pricing or guarantees."
)

MISSED_CALL_STATUSES = {"no-answer", "busy", "failed"}
DEFAULT_MISSED_CALL_TEXT = (
    "Sorry we missed your call. 您好，刚才没能接到您的电话。"
    "Reply to this text and our AI assistant can help you now."
)


def get_openai_client():
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured")
    return OpenAI(api_key=api_key)


def get_twilio_client():
    account_sid = os.getenv("TWILIO_ACCOUNT_SID", "").strip()
    auth_token = os.getenv("TWILIO_AUTH_TOKEN", "").strip()
    if not account_sid or not auth_token:
        raise RuntimeError("Twilio credentials are not configured")
    return Client(account_sid, auth_token)


def xml_response(twiml):
    return Response(str(twiml), mimetype="application/xml")


@app.get("/health")
def health():
    return {"ok": True, "model": MODEL}


@app.post("/sms")
def sms():
    user_text = (request.values.get("Body") or "").strip()
    twiml = MessagingResponse()

    if not user_text:
        return xml_response(twiml)

    try:
        ai = get_openai_client().responses.create(
            model=MODEL,
            instructions=INSTRUCTIONS,
            input=user_text,
            reasoning={"effort": "none"},
            max_output_tokens=200,
        )
        reply = (ai.output_text or "").strip()
        if not reply:
            reply = "Thanks for your message. How can I help?"
    except Exception as exc:
        print(f"OpenAI error: {type(exc).__name__}: {exc}")
        reply = "Sorry, the AI service is temporarily unavailable. Please try again shortly."

    twiml.message(reply[:600])
    return xml_response(twiml)


@app.post("/voice")
def voice():
    """Receive a call and forward it to the owner's real phone."""
    forward_to = os.getenv("FORWARD_TO_PHONE", "").strip()
    response = VoiceResponse()

    if not forward_to:
        response.say("This demo number is not configured for call forwarding yet.")
        return xml_response(response)

    response.dial(
        forward_to,
        timeout=int(os.getenv("RING_TIMEOUT_SECONDS", "20")),
        action="/dial-status",
        method="POST",
    )
    return xml_response(response)


@app.post("/dial-status")
def dial_status():
    """After the forwarded call ends, text the caller if nobody answered."""
    status = (request.values.get("DialCallStatus") or "").strip().lower()
    caller = (request.values.get("From") or "").strip()
    response = VoiceResponse()

    if status in MISSED_CALL_STATUSES and caller:
        from_number = os.getenv("TWILIO_PHONE_NUMBER", "").strip()
        body = os.getenv("MISSED_CALL_TEXT", "").strip() or DEFAULT_MISSED_CALL_TEXT

        try:
            if not from_number:
                raise RuntimeError("TWILIO_PHONE_NUMBER is not configured")

            message = get_twilio_client().messages.create(
                to=caller,
                from_=from_number,
                body=body,
            )
            print(f"Missed-call text sent to {caller}: {message.sid}")
        except Exception as exc:
            print(f"Missed-call SMS error for {caller}: {type(exc).__name__}: {exc}")

        response.say("Sorry we missed your call. We just sent you a text message.")

    return xml_response(response)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8000")), debug=True)
