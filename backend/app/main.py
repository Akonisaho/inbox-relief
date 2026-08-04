from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from starlette.concurrency import run_in_threadpool

from app.config import GMAIL_CREDENTIALS_PATH, GMAIL_TOKEN_PATH
from app.db import SessionLocal, init_models
from app.embeddings import email_to_embedding_text, embed_text
from app.models import Email, Tenant
from app.providers.gmail import GmailProvider
from app.vectorstore import search_similar, upsert_email_vector

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
async def sync_gmail(limit: int | None = 200):
    """limit=None fetches the entire mailbox — slow on a near-full inbox, so
    default to a bounded batch until we're ready for a full historical sync."""
    provider = GmailProvider(str(GMAIL_CREDENTIALS_PATH), str(GMAIL_TOKEN_PATH))
    provider.authenticate()
    emails = await run_in_threadpool(provider.fetch_new_emails, None, limit)

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


@app.get("/index/gmail")
async def index_unembedded_emails():
    """Embed every stored email that hasn't been embedded yet and upsert into Qdrant."""
    async with SessionLocal() as session:
        tenant = await session.scalar(select(Tenant).where(Tenant.name == DEFAULT_TENANT_NAME))
        rows = (
            await session.scalars(select(Email).where(Email.embedded_at.is_(None)))
        ).all()

        indexed = 0
        for row in rows:
            text = email_to_embedding_text(row.subject, row.sender, row.body_text or row.snippet)
            vector = await run_in_threadpool(embed_text, text)
            await run_in_threadpool(
                upsert_email_vector,
                tenant.id,
                row.id,
                vector,
                {
                    "subject": row.subject,
                    "sender": row.sender,
                    "received_at": row.received_at.isoformat(),
                    "snippet": row.snippet,
                },
            )
            row.embedded_at = datetime.now(timezone.utc)
            indexed += 1

        await session.commit()

    return {"indexed": indexed, "skipped_already_embedded": len(rows) - indexed}


@app.get("/search")
async def search_emails(q: str, limit: int = 5):
    """Find past emails semantically similar to a free-text query — proves the RAG retrieval step."""
    async with SessionLocal() as session:
        tenant = await session.scalar(select(Tenant).where(Tenant.name == DEFAULT_TENANT_NAME))

    vector = await run_in_threadpool(embed_text, q)
    results = await run_in_threadpool(search_similar, tenant.id, vector, limit)
    return {"query": q, "results": results}
