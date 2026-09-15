import os

from dotenv import load_dotenv
from flask import Flask, Response, request
from openai import OpenAI
from twilio.twiml.messaging_response import MessagingResponse

load_dotenv()

app = Flask(__name__)
MODEL = os.getenv("OPENAI_MODEL", "gpt-5.6-luna")

INSTRUCTIONS = (
    "You are a concise bilingual SMS receptionist for an AI customer-service company. "
    "Reply in the user's language. Keep replies to 1-3 short sentences. "
    "Be helpful and natural. Do not invent pricing or guarantees."
)


def get_openai_client():
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured")
    return OpenAI(api_key=api_key)


@app.get("/health")
def health():
    return {"ok": True, "model": MODEL}


@app.post("/sms")
def sms():
    user_text = (request.values.get("Body") or "").strip()
    twiml = MessagingResponse()

    if not user_text:
        return Response(str(twiml), mimetype="application/xml")

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
    return Response(str(twiml), mimetype="application/xml")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8000")), debug=True)
