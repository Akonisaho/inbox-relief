from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"))
    email: Mapped[str] = mapped_column(unique=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    tenant: Mapped["Tenant"] = relationship()


class Email(Base):
    __tablename__ = "emails"
    __table_args__ = (UniqueConstraint("provider", "provider_message_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"))

    provider: Mapped[str]
    provider_message_id: Mapped[str]
    thread_id: Mapped[str]
    subject: Mapped[str]
    sender: Mapped[str]
    recipients: Mapped[list] = mapped_column(JSON, default=list)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    snippet: Mapped[str]
    body_text: Mapped[str]
    message_id_header: Mapped[str] = mapped_column(default="")
    labels: Mapped[list] = mapped_column(JSON, default=list)
    is_unread: Mapped[bool] = mapped_column(default=False)

    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    embedded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    urgency: Mapped[str | None] = mapped_column(default=None)
    should_archive: Mapped[bool | None] = mapped_column(default=None)
    confidence: Mapped[float | None] = mapped_column(default=None)
    reasoning: Mapped[str | None] = mapped_column(default=None)
    classified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)


class Correction(Base):
    """A user override of a stored judgment — feeds the correction loop the
    charter calls for (false-archive rate trending to zero as it matures)."""

    __tablename__ = "corrections"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"))
    email_id: Mapped[int] = mapped_column(ForeignKey("emails.id"))

    field: Mapped[str]  # "should_archive" | "urgency"
    previous_value: Mapped[str]
    corrected_value: Mapped[str]
    note: Mapped[str | None] = mapped_column(default=None)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"))
    email_id: Mapped[int | None] = mapped_column(ForeignKey("emails.id"), default=None)

    action: Mapped[str]  # "archive" | "restore" | "classify" | "correction" | "rule_created"
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class Rule(Base):
    """User-defined shortcut that skips LLM classification when it matches
    (e.g. "always archive mail from X"). Applied before classify_email runs."""

    __tablename__ = "rules"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"))

    match_field: Mapped[str]  # "sender" | "subject"
    match_value: Mapped[str]  # substring match, case-insensitive
    should_archive: Mapped[bool]
    urgency: Mapped[str] = mapped_column(default="low")
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
