import json

import ollama

from app.config import INFERENCE_MODEL, OLLAMA_URL
from app.embeddings import email_to_embedding_text, embed_text
from app.vectorstore import search_similar

_client = ollama.Client(host=OLLAMA_URL)

SYSTEM_PROMPT = """You are an email triage assistant for one person's mailbox. \
Given an email and a list of semantically similar past emails from the same \
mailbox, judge it.

- urgency: "high" (needs prompt attention), "medium", or "low"
- should_archive: true if this looks like low-value mail (marketing, job \
alerts, automated notifications, newsletters) that's safe to archive; false \
if it's a real message the user should keep visible
- confidence: a number 0.0-1.0 for how sure you are
- reasoning: one short sentence explaining the judgment
- due_date: if the email mentions an explicit deadline, due date, submission \
date, or event date that the user needs to act by (e.g. "assessment due \
Friday", "submit by 15 August", "meeting on Monday at 2pm") — resolve it to \
an absolute date in "YYYY-MM-DD" format using the email's received date \
(given below) to interpret relative phrases like "Friday" or "in 3 days". \
If no such date is mentioned, use null.

Critical rule: a personal, back-and-forth conversation with a real person \
(family, friends, partner, colleagues) is NEVER should_archive=true, \
regardless of subject line or how mundane the content seems — these are \
exactly the messages this system exists to protect, not clear away. Only \
recommend archiving mail that is automated, one-directional, or from a \
company/organization (newsletters, alerts, marketing, notifications, \
receipts). When in doubt about whether a sender is a real person or an \
automated/organizational sender, prefer should_archive=false.

Respond with ONLY a JSON object, no other text:
{"urgency": "...", "should_archive": true_or_false, "confidence": 0.0, "reasoning": "...", "due_date": "YYYY-MM-DD" or null}
"""


class ClassificationError(Exception):
    pass


def classify_email(
    tenant_id: int, subject: str, sender: str, body_text: str, snippet: str, received_at
) -> dict:
    text = email_to_embedding_text(subject, sender, body_text or snippet)
    vector = embed_text(text)
    similar = search_similar(tenant_id, vector, limit=5)
    similar_context = "\n".join(f"- {s['subject']!r} from {s['sender']}" for s in similar) or "(none yet)"

    prompt = (
        f"{SYSTEM_PROMPT}\n\n"
        f"Similar past emails in this mailbox:\n{similar_context}\n\n"
        f"Email received on: {received_at.date().isoformat()}\n"
        f"Email to judge:\nFrom: {sender}\nSubject: {subject}\n\n{(body_text or snippet)[:2000]}"
    )

    response = _client.generate(model=INFERENCE_MODEL, prompt=prompt, format="json")
    try:
        result = json.loads(response["response"])
    except json.JSONDecodeError as e:
        raise ClassificationError(f"model did not return valid JSON: {response['response']!r}") from e

    missing = {"urgency", "should_archive", "confidence", "reasoning"} - result.keys()
    if missing:
        raise ClassificationError(f"model response missing fields {missing}: {result!r}")

    result.setdefault("due_date", None)
    return result
