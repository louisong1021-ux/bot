import json
import os

from openai import OpenAI

MODEL = os.getenv("OPENAI_MODEL", "gpt-5.6-luna")
COMPANY_NAME = os.getenv("DEMO_COMPANY_NAME", "AI Front Desk Demo")

SYSTEM_PROMPT = f"""
You are the SMS receptionist for {COMPANY_NAME}, a company that provides AI customer service and AI front-desk solutions to small and medium businesses.

Your job:
1. Reply naturally and helpfully to inbound SMS messages.
2. Follow the user's language. If they write Chinese, reply in Chinese. If English, reply in English. If mixed, match naturally.
3. Keep the SMS reply concise: usually 1-3 short sentences and preferably under 320 characters. No markdown, tables, headings, or emoji spam.
4. Explain capabilities such as AI SMS support, AI phone receptionist, lead capture, appointment workflows, CRM/Notion integration, bilingual support, and human handoff.
5. Do not invent a firm price, guarantee, integration, legal claim, or feature that has not been confirmed. If pricing is asked, explain that pricing depends on usage and workflow and ask one useful qualification question.
6. Gradually qualify genuine business prospects. Useful fields are: name, company, industry, main problem/need, and preferred callback time. Do not interrogate the user; ask at most one qualification question per reply.
7. Treat the sender's phone number as already known, so do not ask them for their phone number.
8. If the user asks for a human, a quote, implementation, a demo, or shows clear purchase intent, set human_handoff=true.
9. The 'lead' object should summarize only information actually provided or reasonably established in the conversation. Unknown fields must be null.
10. Lead score: cold = browsing/general question, warm = business owner/decision maker with a real use case, hot = asks for demo/quote/setup/human contact or indicates near-term intent.
""".strip()

SCHEMA = {
    "type": "object",
    "properties": {
        "reply": {"type": "string"},
        "human_handoff": {"type": "boolean"},
        "lead": {
            "type": "object",
            "properties": {
                "is_lead": {"type": "boolean"},
                "name": {"type": ["string", "null"]},
                "company": {"type": ["string", "null"]},
                "industry": {"type": ["string", "null"]},
                "need": {"type": ["string", "null"]},
                "preferred_callback": {"type": ["string", "null"]},
                "summary": {"type": ["string", "null"]},
                "score": {"type": "string", "enum": ["cold", "warm", "hot"]}
            },
            "required": [
                "is_lead", "name", "company", "industry", "need",
                "preferred_callback", "summary", "score"
            ],
            "additionalProperties": False
        }
    },
    "required": ["reply", "human_handoff", "lead"],
    "additionalProperties": False
}


def _client():
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured")
    return OpenAI(api_key=api_key, timeout=10.0, max_retries=1)


def respond(history):
    response = _client().responses.create(
        model=MODEL,
        instructions=SYSTEM_PROMPT,
        input=history,
        reasoning={"effort": "none"},
        max_output_tokens=500,
        text={
            "verbosity": "low",
            "format": {
                "type": "json_schema",
                "name": "sms_receptionist_response",
                "strict": True,
                "schema": SCHEMA
            }
        },
        store=False
    )

    data = json.loads(response.output_text)
    reply = (data.get("reply") or "").strip()
    if not reply:
        reply = "Thanks for your message. How can I help with your business today?"

    if len(reply) > 600:
        reply = reply[:597].rstrip() + "..."

    data["reply"] = reply
    return data
