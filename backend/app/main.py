import re
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sqlalchemy import Date, case, cast, extract, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from starlette.concurrency import run_in_threadpool

from app.chat import extract_rule, handle_chat
from app.config import GMAIL_CREDENTIALS_PATH, GMAIL_TOKEN_PATH
from app.db import SessionLocal, init_models
from app.embeddings import email_to_embedding_text, embed_text
from app.inference import ClassificationError, classify_email
from app.models import AuditLog, Correction, Email, Rule, Tenant
from app.providers.gmail import GmailProvider
from app.vectorstore import search_similar, upsert_email_vector

DEFAULT_TENANT_NAME = "default"


def _gmail_provider() -> GmailProvider:
    provider = GmailProvider(str(GMAIL_CREDENTIALS_PATH), str(GMAIL_TOKEN_PATH))
    provider.authenticate()
    return provider


async def _get_default_tenant(session):
    return await session.scalar(select(Tenant).where(Tenant.name == DEFAULT_TENANT_NAME))


def _log_audit(session, tenant_id: int, action: str, email_id: int | None = None, detail: dict | None = None):
    session.add(AuditLog(tenant_id=tenant_id, action=action, email_id=email_id, detail=detail or {}))


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
            ingestion_fields = {
                "thread_id": e.thread_id,
                "subject": e.subject,
                "sender": e.sender,
                "recipients": e.recipients,
                "received_at": e.received_at,
                "snippet": e.snippet,
                "body_text": e.body_text,
                "message_id_header": e.message_id_header,
                "labels": e.labels,
                "is_unread": e.is_unread,
            }
            stmt = (
                pg_insert(Email)
                .values(
                    tenant_id=tenant.id,
                    provider=e.provider,
                    provider_message_id=e.provider_message_id,
                    **ingestion_fields,
                )
                # Update on conflict rather than no-op: this self-heals rows that
                # predate a new ingestion field (e.g. message_id_header) without
                # ever touching app-owned state (archived_at, classification, etc).
                .on_conflict_do_update(
                    index_elements=["provider", "provider_message_id"],
                    set_=ingestion_fields,
                )
            )
            await session.execute(stmt)
            stored += 1

        await session.commit()

    return {"fetched": len(emails), "newly_stored_or_updated": stored}


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


def _matches_rule(rule: Rule, subject: str, sender: str) -> bool:
    haystack = (subject if rule.match_field == "subject" else sender).lower()
    return rule.match_value.lower() in haystack


def _parse_due_date(value):
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None  # model occasionally returns a malformed date — treat as none rather than fail


AUTO_ARCHIVE_CONFIDENCE_THRESHOLD = 0.85


@app.get("/classify/gmail")
async def classify_unclassified_emails(limit: int = 20):
    """Judge urgency + archive-worthiness for unclassified emails via local LLM + RAG.
    Bounded by default — CPU inference is much slower than embedding. Rules are
    checked first and skip the LLM entirely when matched. Anything judged
    should_archive at or above AUTO_ARCHIVE_CONFIDENCE_THRESHOLD gets archived
    immediately — this is the confidence gate: only near-certain, low-value mail
    archives itself, everything else waits for a human decision."""
    provider = None  # lazily authenticated only if something actually needs archiving

    async with SessionLocal() as session:
        tenant = await _get_default_tenant(session)
        rows = (
            await session.scalars(
                select(Email)
                .where(Email.classified_at.is_(None))
                .order_by(Email.received_at.desc())
                .limit(limit)
            )
        ).all()
        rules = (await session.scalars(select(Rule).where(Rule.tenant_id == tenant.id))).all()

        classified, rule_matched, auto_archived, failed = 0, 0, 0, []
        for row in rows:
            matched_rule = next(
                (r for r in rules if _matches_rule(r, row.subject, row.sender)), None
            )
            if matched_rule:
                row.urgency = matched_rule.urgency
                row.should_archive = matched_rule.should_archive
                row.confidence = 1.0
                row.reasoning = f"Matched rule: {matched_rule.match_field}={matched_rule.match_value!r}"
                row.due_date = None
                row.classified_at = datetime.now(timezone.utc)
                rule_matched += 1
            else:
                try:
                    result = await run_in_threadpool(
                        classify_email,
                        tenant.id, row.subject, row.sender, row.body_text, row.snippet, row.received_at,
                    )
                except ClassificationError as e:
                    failed.append({"id": row.id, "subject": row.subject, "error": str(e)})
                    continue

                row.urgency = result["urgency"]
                row.should_archive = bool(result["should_archive"])
                row.confidence = float(result["confidence"])
                row.reasoning = result["reasoning"]
                row.due_date = _parse_due_date(result.get("due_date"))
                row.classified_at = datetime.now(timezone.utc)
                classified += 1

            if row.should_archive and row.confidence >= AUTO_ARCHIVE_CONFIDENCE_THRESHOLD:
                if provider is None:
                    provider = await run_in_threadpool(_gmail_provider)
                await run_in_threadpool(provider.archive, row.provider_message_id)
                row.archived_at = datetime.now(timezone.utc)
                _log_audit(
                    session, row.tenant_id, "archive", row.id,
                    {"subject": row.subject, "auto": True, "via": "classify", "confidence": row.confidence},
                )
                auto_archived += 1

        await session.commit()

    return {
        "classified": classified,
        "rule_matched": rule_matched,
        "auto_archived": auto_archived,
        "failed": failed,
    }


@app.get("/emails/classified")
async def list_classified_emails():
    async with SessionLocal() as session:
        rows = (
            await session.scalars(
                select(Email)
                .where(Email.classified_at.is_not(None))
                .order_by(Email.received_at.desc())
            )
        ).all()
        return [
            {
                "id": row.id,
                "provider_message_id": row.provider_message_id,
                "message_id_header": row.message_id_header,
                "subject": row.subject,
                "sender": row.sender,
                "urgency": row.urgency,
                "should_archive": row.should_archive,
                "confidence": row.confidence,
                "reasoning": row.reasoning,
                "due_date": row.due_date.isoformat() if row.due_date else None,
                "archived_at": row.archived_at.isoformat() if row.archived_at else None,
            }
            for row in rows
        ]


@app.get("/emails/{email_id}")
async def get_email(email_id: int):
    """Full content for in-app reading, fetched on demand rather than bundled
    into list responses (body text would bloat those for no benefit)."""
    async with SessionLocal() as session:
        row = await session.get(Email, email_id)
        if not row:
            raise HTTPException(404, "email not found")
        return {
            "id": row.id,
            "message_id_header": row.message_id_header,
            "subject": row.subject,
            "sender": row.sender,
            "recipients": row.recipients,
            "received_at": row.received_at.isoformat(),
            "body_text": row.body_text,
            "urgency": row.urgency,
            "should_archive": row.should_archive,
            "reasoning": row.reasoning,
            "due_date": row.due_date.isoformat() if row.due_date else None,
            "archived_at": row.archived_at.isoformat() if row.archived_at else None,
        }


@app.post("/emails/{email_id}/archive")
async def archive_one(email_id: int):
    async with SessionLocal() as session:
        row = await session.get(Email, email_id)
        if not row:
            raise HTTPException(404, "email not found")
        if row.archived_at:
            return {"already_archived": True}

        provider = await run_in_threadpool(_gmail_provider)
        await run_in_threadpool(provider.archive, row.provider_message_id)

        row.archived_at = datetime.now(timezone.utc)
        _log_audit(session, row.tenant_id, "archive", row.id, {"subject": row.subject})
        await session.commit()

    return {"archived": True, "email_id": email_id}


@app.post("/emails/{email_id}/restore")
async def restore_one(email_id: int):
    async with SessionLocal() as session:
        row = await session.get(Email, email_id)
        if not row:
            raise HTTPException(404, "email not found")
        if not row.archived_at:
            return {"already_active": True}

        provider = await run_in_threadpool(_gmail_provider)
        await run_in_threadpool(provider.restore, row.provider_message_id)

        row.archived_at = None
        _log_audit(session, row.tenant_id, "restore", row.id, {"subject": row.subject})
        await session.commit()

    return {"restored": True, "email_id": email_id}


@app.get("/archive/candidates")
async def archive_candidates(threshold: float = 0.7):
    """Preview what /archive/auto would archive, without touching anything."""
    async with SessionLocal() as session:
        rows = (
            await session.scalars(
                select(Email).where(
                    Email.classified_at.is_not(None),
                    Email.should_archive.is_(True),
                    Email.confidence >= threshold,
                    Email.archived_at.is_(None),
                )
            )
        ).all()
        return {
            "count": len(rows),
            "emails": [
                {"id": r.id, "subject": r.subject, "sender": r.sender, "confidence": r.confidence}
                for r in rows
            ],
        }


@app.post("/archive/auto")
async def archive_auto(threshold: float = 0.7):
    """Actually execute the bulk archive for every high-confidence should_archive email."""
    async with SessionLocal() as session:
        rows = (
            await session.scalars(
                select(Email).where(
                    Email.classified_at.is_not(None),
                    Email.should_archive.is_(True),
                    Email.confidence >= threshold,
                    Email.archived_at.is_(None),
                )
            )
        ).all()

        provider = await run_in_threadpool(_gmail_provider)
        archived = 0
        for row in rows:
            await run_in_threadpool(provider.archive, row.provider_message_id)
            row.archived_at = datetime.now(timezone.utc)
            _log_audit(session, row.tenant_id, "archive", row.id, {"subject": row.subject, "auto": True})
            archived += 1

        await session.commit()

    return {"archived": archived}


class CorrectionRequest(BaseModel):
    field: str  # "should_archive" | "urgency"
    corrected_value: str
    note: str | None = None


@app.post("/emails/{email_id}/correct")
async def correct_one(email_id: int, body: CorrectionRequest):
    if body.field not in ("should_archive", "urgency"):
        raise HTTPException(400, "field must be 'should_archive' or 'urgency'")

    async with SessionLocal() as session:
        row = await session.get(Email, email_id)
        if not row:
            raise HTTPException(404, "email not found")

        previous_value = str(getattr(row, body.field))
        session.add(
            Correction(
                tenant_id=row.tenant_id,
                email_id=row.id,
                field=body.field,
                previous_value=previous_value,
                corrected_value=body.corrected_value,
                note=body.note,
            )
        )

        if body.field == "should_archive":
            new_value = body.corrected_value.lower() == "true"
            row.should_archive = new_value
            if new_value is False and row.archived_at:
                provider = await run_in_threadpool(_gmail_provider)
                await run_in_threadpool(provider.restore, row.provider_message_id)
                row.archived_at = None
        else:
            row.urgency = body.corrected_value

        _log_audit(
            session,
            row.tenant_id,
            "correction",
            row.id,
            {"field": body.field, "previous": previous_value, "corrected": body.corrected_value},
        )
        await session.commit()

    return {"corrected": True, "email_id": email_id, "field": body.field}


@app.get("/digest")
async def daily_digest():
    """Emails needing attention TODAY: unarchived, not low-urgency, received today."""
    today = datetime.now(timezone.utc).date()

    async with SessionLocal() as session:
        tenant = await _get_default_tenant(session)

        needs_attention = (
            await session.scalars(
                select(Email)
                .where(
                    Email.archived_at.is_(None),
                    Email.classified_at.is_not(None),
                    Email.urgency.in_(["high", "medium"]),
                    cast(Email.received_at, Date) == today,
                )
                .order_by(Email.urgency.asc(), Email.received_at.desc())
                .limit(50)
            )
        ).all()

        total = await session.scalar(
            select(func.count()).select_from(Email).where(Email.tenant_id == tenant.id)
        )
        archived = await session.scalar(
            select(func.count()).select_from(Email).where(
                Email.tenant_id == tenant.id, Email.archived_at.is_not(None)
            )
        )
        unclassified = await session.scalar(
            select(func.count()).select_from(Email).where(
                Email.tenant_id == tenant.id, Email.classified_at.is_(None)
            )
        )
        received_today = await session.scalar(
            select(func.count()).select_from(Email).where(
                Email.tenant_id == tenant.id, cast(Email.received_at, Date) == today
            )
        )
        declutter_bytes = await session.scalar(
            select(func.coalesce(func.sum(func.length(Email.body_text)), 0)).where(
                Email.tenant_id == tenant.id, Email.archived_at.is_not(None)
            )
        )

        def _serialize(r):
            return {
                "id": r.id,
                "provider_message_id": r.provider_message_id,
                "message_id_header": r.message_id_header,
                "subject": r.subject,
                "sender": r.sender,
                "snippet": r.snippet,
                "urgency": r.urgency,
                "reasoning": r.reasoning,
                "due_date": r.due_date.isoformat() if r.due_date else None,
                "received_at": r.received_at.isoformat(),
            }

        return {
            "mailbox_total": total,
            "archived_total": archived,
            "inbox_count": total - archived,
            "unclassified_total": unclassified,
            "received_today": received_today,
            # Archiving removes Gmail's Inbox label — it does NOT delete anything or
            # reduce your actual storage quota (Gmail counts All Mail + Trash the same).
            # This is an approximate measure of how much has been decluttered from view,
            # not storage freed.
            "declutter_kb_approx": round(declutter_bytes / 1024, 1),
            "needs_immediate_attention": [
                _serialize(r) for r in needs_attention if r.urgency == "high"
            ],
            "important_today": [
                _serialize(r) for r in needs_attention if r.urgency == "medium"
            ],
        }


class ChatRequest(BaseModel):
    message: str
    email_id: int | None = None


@app.post("/chat")
async def chat(body: ChatRequest):
    async with SessionLocal() as session:
        tenant = await _get_default_tenant(session)
        result = await run_in_threadpool(handle_chat, body.message, tenant.id)
        intent = result["intent"]

        if intent == "correction":
            if body.email_id is None:
                return {"intent": intent, "error": "correction requires email_id"}
            # Simplest correction: treat the message as "don't archive this".
            row = await session.get(Email, body.email_id)
            if not row:
                raise HTTPException(404, "email not found")
            previous = str(row.should_archive)
            row.should_archive = False
            if row.archived_at:
                provider = await run_in_threadpool(_gmail_provider)
                await run_in_threadpool(provider.restore, row.provider_message_id)
                row.archived_at = None
            session.add(
                Correction(
                    tenant_id=row.tenant_id,
                    email_id=row.id,
                    field="should_archive",
                    previous_value=previous,
                    corrected_value="False",
                    note=body.message,
                )
            )
            _log_audit(session, row.tenant_id, "correction", row.id, {"via": "chat", "message": body.message})
            await session.commit()
            return {"intent": intent, "applied_to_email_id": row.id}

        if intent == "rule":
            rule_data = result["rule"]
            rule = Rule(
                tenant_id=tenant.id,
                match_field=rule_data["match_field"],
                match_value=rule_data["match_value"],
                should_archive=bool(rule_data["should_archive"]),
                urgency=rule_data.get("urgency", "low"),
                source_text=body.message,
            )
            session.add(rule)
            _log_audit(session, tenant.id, "rule_created", detail={**rule_data, "source_text": body.message})
            await session.commit()
            return {"intent": intent, "rule": rule_data}

        return {"intent": "question", "answer": result.get("answer")}


@app.get("/rules")
async def list_rules():
    async with SessionLocal() as session:
        rows = (await session.scalars(select(Rule))).all()
        return [
            {
                "id": r.id,
                "match_field": r.match_field,
                "match_value": r.match_value,
                "should_archive": r.should_archive,
                "urgency": r.urgency,
                "source_text": r.source_text,
            }
            for r in rows
        ]


class RuleRequest(BaseModel):
    match_field: str  # "sender" | "subject"
    match_value: str
    should_archive: bool
    urgency: str = "low"


@app.post("/rules")
async def create_rule(body: RuleRequest):
    if body.match_field not in ("sender", "subject"):
        raise HTTPException(400, "match_field must be 'sender' or 'subject'")
    if body.urgency not in ("high", "medium", "low"):
        raise HTTPException(400, "urgency must be 'high', 'medium', or 'low'")

    async with SessionLocal() as session:
        tenant = await _get_default_tenant(session)
        rule = Rule(
            tenant_id=tenant.id,
            match_field=body.match_field,
            match_value=body.match_value,
            should_archive=body.should_archive,
            urgency=body.urgency,
        )
        session.add(rule)
        _log_audit(session, tenant.id, "rule_created", detail=body.model_dump())
        await session.commit()
        await session.refresh(rule)

    return {
        "id": rule.id,
        "match_field": rule.match_field,
        "match_value": rule.match_value,
        "should_archive": rule.should_archive,
        "urgency": rule.urgency,
        "source_text": rule.source_text,
    }


class RuleFromTextRequest(BaseModel):
    text: str


@app.post("/rules/from_text")
async def create_rule_from_text(body: RuleFromTextRequest):
    """Write a rule in plain language instead of filling in a form — same
    extraction the chat 'rule' intent uses."""
    rule_data = await run_in_threadpool(extract_rule, body.text)

    async with SessionLocal() as session:
        tenant = await _get_default_tenant(session)
        rule = Rule(
            tenant_id=tenant.id,
            match_field=rule_data["match_field"],
            match_value=rule_data["match_value"],
            should_archive=bool(rule_data["should_archive"]),
            urgency=rule_data.get("urgency", "low"),
            source_text=body.text,
        )
        session.add(rule)
        _log_audit(session, tenant.id, "rule_created", detail={**rule_data, "source_text": body.text})
        await session.commit()
        await session.refresh(rule)

    return {
        "id": rule.id,
        "match_field": rule.match_field,
        "match_value": rule.match_value,
        "should_archive": rule.should_archive,
        "urgency": rule.urgency,
        "source_text": rule.source_text,
    }


@app.delete("/rules/{rule_id}")
async def delete_rule(rule_id: int):
    async with SessionLocal() as session:
        rule = await session.get(Rule, rule_id)
        if not rule:
            raise HTTPException(404, "rule not found")
        detail = {"match_field": rule.match_field, "match_value": rule.match_value}
        await session.delete(rule)
        _log_audit(session, rule.tenant_id, "rule_deleted", detail=detail)
        await session.commit()
    return {"deleted": True}


@app.get("/calendar")
async def calendar(year: int | None = None, month: int | None = None):
    """Per-day counts for a given month: how many arrived, how many got
    archived, how many are still unread."""
    now = datetime.now(timezone.utc)
    year = year or now.year
    month = month or now.month

    async with SessionLocal() as session:
        tenant = await _get_default_tenant(session)

        day = cast(Email.received_at, Date)
        stmt = (
            select(
                day.label("day"),
                func.count().label("received"),
                func.sum(case((Email.archived_at.is_not(None), 1), else_=0)).label("archived"),
                func.sum(case((Email.is_unread.is_(True), 1), else_=0)).label("unread"),
                func.sum(case((Email.urgency == "high", 1), else_=0)).label("high"),
            )
            .where(
                Email.tenant_id == tenant.id,
                extract("year", Email.received_at) == year,
                extract("month", Email.received_at) == month,
            )
            .group_by(day)
            .order_by(day)
        )
        rows = (await session.execute(stmt)).all()

        return {
            "year": year,
            "month": month,
            "days": [
                {
                    "date": r.day.isoformat(),
                    "received": r.received,
                    "archived": r.archived,
                    "unread": r.unread,
                    "high": r.high,
                }
                for r in rows
            ],
        }


@app.get("/calendar/day")
async def calendar_day(date: str):
    """Full email list for one calendar day (drill-down from /calendar)."""
    try:
        parsed_date = datetime.strptime(date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(400, "date must be YYYY-MM-DD")

    async with SessionLocal() as session:
        tenant = await _get_default_tenant(session)
        day_col = cast(Email.received_at, Date)
        rows = (
            await session.scalars(
                select(Email)
                .where(Email.tenant_id == tenant.id, day_col == parsed_date)
                .order_by(Email.received_at.desc())
            )
        ).all()
        return {
            "date": date,
            "emails": [
                {
                    "id": r.id,
                    "subject": r.subject,
                    "sender": r.sender,
                    "urgency": r.urgency,
                    "is_unread": r.is_unread,
                    "archived_at": r.archived_at.isoformat() if r.archived_at else None,
                    "received_at": r.received_at.isoformat(),
                }
                for r in rows
            ],
        }


@app.get("/senders/never-replied")
async def never_replied_senders(min_count: int = 2):
    """Senders where you've never sent a message in any of their threads —
    a strong signal of promotional/notification mail worth bulk-archiving,
    learned from your actual reply history rather than guessed."""
    provider = await run_in_threadpool(_gmail_provider)
    own_email = await run_in_threadpool(provider.get_own_email_address)

    async with SessionLocal() as session:
        tenant = await _get_default_tenant(session)

        replied_threads = select(Email.thread_id).where(
            Email.tenant_id == tenant.id, Email.sender.ilike(f"%{own_email}%")
        )
        stmt = (
            select(Email.sender, func.count().label("count"))
            .where(
                Email.tenant_id == tenant.id,
                ~Email.sender.ilike(f"%{own_email}%"),
                ~Email.thread_id.in_(replied_threads),
            )
            .group_by(Email.sender)
            .having(func.count() >= min_count)
            .order_by(func.count().desc())
        )
        rows = (await session.execute(stmt)).all()

        return {
            "own_email": own_email,
            "senders": [{"sender": r.sender, "count": r.count} for r in rows],
        }


class ApplyNeverRepliedRequest(BaseModel):
    senders: list[str]


@app.post("/senders/never-replied/apply")
async def apply_never_replied_rules(body: ApplyNeverRepliedRequest):
    """Bulk-create archive rules for chosen never-replied senders — a
    reviewable action, not silent automation: the caller picks which
    senders from the suggestion list to actually apply."""
    async with SessionLocal() as session:
        tenant = await _get_default_tenant(session)
        created = []
        for sender in body.senders:
            match = re.search(r"<([^>]+)>", sender)
            address = match.group(1) if match else sender
            rule = Rule(
                tenant_id=tenant.id,
                match_field="sender",
                match_value=address,
                should_archive=True,
                urgency="low",
                source_text=f"Suggested: you've never replied to {address}",
            )
            session.add(rule)
            created.append(address)
        _log_audit(session, tenant.id, "rule_created", detail={"bulk_never_replied": created})
        await session.commit()

    return {"created": len(created)}
