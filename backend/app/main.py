from fastapi import FastAPI

from app.config import GMAIL_CREDENTIALS_PATH, GMAIL_TOKEN_PATH
from app.providers.gmail import GmailProvider

app = FastAPI(title="Inbox Relief — Ingestion (dev)")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/ingest/gmail/sync")
def sync_gmail():
    """Day 1-2 proof-of-loop: authenticate, fetch recent emails, return them.
    No persistence yet — Postgres wiring comes once this loop is proven."""
    provider = GmailProvider(str(GMAIL_CREDENTIALS_PATH), str(GMAIL_TOKEN_PATH))
    provider.authenticate()
    emails = provider.fetch_new_emails()
    return {
        "count": len(emails),
        "emails": [
            {
                "id": e.provider_message_id,
                "subject": e.subject,
                "sender": e.sender,
                "received_at": e.received_at.isoformat(),
                "snippet": e.snippet,
            }
            for e in emails
        ],
    }
