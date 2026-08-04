import json

import ollama

from app.config import INFERENCE_MODEL, OLLAMA_URL
from app.embeddings import embed_text
from app.vectorstore import search_similar

_client = ollama.Client(host=OLLAMA_URL)

INTENT_PROMPT = """Classify the intent of this message from a user talking to \
their email triage assistant.

Message: {message}

- "correction": the user is correcting a specific past judgment about email(s) \
that already exist (e.g. "that shouldn't have been archived", "that was actually urgent")
- "rule": the user is explicitly setting a standing POLICY for how FUTURE \
emails should be handled — look for words like "always", "never", "from now \
on", "whenever". Examples: "always archive emails from noreply@x.com", "mark \
anything from my boss as high urgency"
- "question": the user is asking, searching, or wondering about their inbox — \
this includes ANY message phrased as a question (containing "?", "any", "do \
I have", "show me", "is there", "did I get"), even if it mentions a topic \
that could also sound rule-like. "Any emails about X?" is a QUESTION about \
existing mail, not a rule about future mail — do not confuse the two.

When genuinely ambiguous, prefer "question" — it's the safe default and \
never mutates data, unlike "rule".

Respond with ONLY JSON: {{"intent": "correction" | "rule" | "question"}}
"""

RULE_EXTRACTION_PROMPT = """Extract a standing email rule from this user message.

Message: {message}

Respond with ONLY JSON:
{{"match_field": "sender" | "subject", "match_value": "...", "should_archive": true_or_false, "urgency": "high" | "medium" | "low"}}
"""


def classify_intent(message: str) -> str:
    response = _client.generate(
        model=INFERENCE_MODEL, prompt=INTENT_PROMPT.format(message=message), format="json"
    )
    result = json.loads(response["response"])
    return result.get("intent", "question")


def extract_rule(message: str) -> dict:
    response = _client.generate(
        model=INFERENCE_MODEL, prompt=RULE_EXTRACTION_PROMPT.format(message=message), format="json"
    )
    return json.loads(response["response"])


def answer_question(message: str, tenant_id: int) -> str:
    vector = embed_text(message)
    similar = search_similar(tenant_id, vector, limit=5)
    context = (
        "\n".join(
            f"- {s['subject']!r} from {s['sender']} (received {s['received_at']})" for s in similar
        )
        or "(no relevant emails found)"
    )
    prompt = (
        "You are an email assistant. Using only the context below, answer the "
        f"user's question concisely.\n\nRelevant emails:\n{context}\n\n"
        f"Question: {message}\n\nAnswer:"
    )
    response = _client.generate(model=INFERENCE_MODEL, prompt=prompt)
    return response["response"].strip()
