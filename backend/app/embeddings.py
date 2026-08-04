import ollama

from app.config import EMBEDDING_MODEL, OLLAMA_URL

_client = ollama.Client(host=OLLAMA_URL)


def embed_text(text: str) -> list[float]:
    response = _client.embeddings(model=EMBEDDING_MODEL, prompt=text)
    return response["embedding"]


def email_to_embedding_text(subject: str, sender: str, body_text: str) -> str:
    # Cap body length — embedding models have a limited context window and
    # the lead paragraph carries most of an email's topical signal anyway.
    return f"From: {sender}\nSubject: {subject}\n\n{body_text[:2000]}"
