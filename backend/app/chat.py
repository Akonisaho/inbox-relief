import json

import ollama

from app.config import CHAT_MODEL, OLLAMA_URL
from app.embeddings import embed_text
from app.vectorstore import search_similar

_client = ollama.Client(host=OLLAMA_URL)

CHAT_PROMPT = """You are an email triage assistant. A user is messaging you about \
their inbox. Using the relevant past emails below as context, respond in ONE step:

1. Classify their intent:
   - "correction": correcting a specific past judgment about an email that already exists
   - "rule": explicitly setting a standing policy for FUTURE emails — look for \
"always", "never", "from now on", "whenever"
   - "question": asking, searching, or wondering about their inbox — this includes \
ANY message phrased as a question ("?", "any", "do I have", "show me", "is there"). \
When genuinely ambiguous, prefer "question" — it's the safe, non-mutating default.

2. Based on the intent, fill in ONLY the matching field, leave the others null:
   - if "question": fill "answer" with a concise answer using the context below
   - if "rule": fill "rule" with the standing policy to create
   - if "correction": leave both null (the caller applies it directly)

Relevant past emails:
{context}

Message: {message}

Respond with ONLY this JSON shape:
{{"intent": "correction" | "rule" | "question", "answer": "..." or null, "rule": \
{{"match_field": "sender" | "subject", "match_value": "...", "should_archive": true_or_false, \
"urgency": "high" | "medium" | "low"}} or null}}
"""


RULE_EXTRACTION_PROMPT = """Extract a standing email rule from this text, written \
in the user's own words.

Text: {text}

Respond with ONLY JSON:
{{"match_field": "sender" | "subject", "match_value": "...", "should_archive": true_or_false, "urgency": "high" | "medium" | "low"}}
"""


def extract_rule(text: str) -> dict:
    """Used when the caller already knows it's a rule (e.g. a dedicated
    'write a rule' box) — no intent classification needed, unlike handle_chat."""
    response = _client.generate(
        model=CHAT_MODEL, prompt=RULE_EXTRACTION_PROMPT.format(text=text), format="json"
    )
    return json.loads(response["response"])


def handle_chat(message: str, tenant_id: int) -> dict:
    """Single LLM call covering intent classification + the intent's payload —
    previously this was two sequential calls (classify, then act), roughly
    doubling latency for every chat turn."""
    vector = embed_text(message)
    similar = search_similar(tenant_id, vector, limit=5)
    context = (
        "\n".join(
            f"- {s['subject']!r} from {s['sender']} (received {s['received_at']})" for s in similar
        )
        or "(no relevant emails found)"
    )

    response = _client.generate(
        model=CHAT_MODEL,
        prompt=CHAT_PROMPT.format(context=context, message=message),
        format="json",
    )
    result = json.loads(response["response"])
    result.setdefault("intent", "question")
    return result
