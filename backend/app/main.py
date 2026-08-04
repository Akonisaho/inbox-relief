from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.config import GMAIL_CREDENTIALS_PATH, GMAIL_TOKEN_PATH
from app.db import SessionLocal, init_models
from app.models import Email, Tenant
from app.providers.gmail import GmailProvider

DEFAULT_TENANT_NAME = "default"


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_models()
    async with SessionLocal() as session:
        existing = await session.scalar(select(Tenant).where(Tenant.name == DEFAULT_TENANT_NAME))
        if not existing:
            session.add(Tenant(name=DEFAULT_TENANT_NAME))
            await session.commit()
    yield


app = FastAPI(title="Inbox Relief — Ingestion (dev)", lifespan=lifespan)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/ingest/gmail/sync")
async def sync_gmail():
    provider = GmailProvider(str(GMAIL_CREDENTIALS_PATH), str(GMAIL_TOKEN_PATH))
    provider.authenticate()
    emails = provider.fetch_new_emails()

    async with SessionLocal() as session:
        tenant = await session.scalar(select(Tenant).where(Tenant.name == DEFAULT_TENANT_NAME))

        stored = 0
        for e in emails:
            stmt = (
                pg_insert(Email)
                .values(
                    tenant_id=tenant.id,
                    provider=e.provider,
                    provider_message_id=e.provider_message_id,
                    thread_id=e.thread_id,
                    subject=e.subject,
                    sender=e.sender,
                    recipients=e.recipients,
                    received_at=e.received_at,
                    snippet=e.snippet,
                    body_text=e.body_text,
                    labels=e.labels,
                    is_unread=e.is_unread,
                )
                .on_conflict_do_nothing(index_elements=["provider", "provider_message_id"])
            )
            result = await session.execute(stmt)
            stored += result.rowcount

        await session.commit()

    return {"fetched": len(emails), "newly_stored": stored}


@app.get("/emails")
async def list_emails():
    async with SessionLocal() as session:
        rows = (await session.scalars(select(Email).order_by(Email.received_at.desc()))).all()
        return [
            {
                "id": row.id,
                "provider": row.provider,
                "subject": row.subject,
                "sender": row.sender,
                "received_at": row.received_at.isoformat(),
                "is_unread": row.is_unread,
                "archived_at": row.archived_at.isoformat() if row.archived_at else None,
            }
            for row in rows
        ]
