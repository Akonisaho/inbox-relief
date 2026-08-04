from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class NormalizedEmail:
    """Provider-agnostic shape every downstream service (embedding, inference,
    archive, chat, frontend) is written against — never a raw Gmail/Graph payload."""

    provider: str          # "gmail" | "outlook"
    provider_message_id: str
    thread_id: str
    subject: str
    sender: str
    recipients: list[str]
    received_at: datetime
    snippet: str
    body_text: str
    message_id_header: str = ""  # RFC822 Message-ID — used for reliable deep-linking
    labels: list[str] = field(default_factory=list)
    is_unread: bool = False


class MailProvider(ABC):
    """One interface every mail provider adapter implements, so ingestion,
    embedding, inference, archiving, and the frontend never branch on
    which provider an email came from."""

    @abstractmethod
    def authenticate(self) -> None:
        """Establish credentials (OAuth flow, token refresh, etc.)."""

    @abstractmethod
    def get_own_email_address(self) -> str:
        """The authenticated mailbox's own address — used to detect whether
        the user ever replied in a thread (sender == own address)."""

    @abstractmethod
    def fetch_new_emails(self, since: datetime | None = None) -> list[NormalizedEmail]:
        """Return normalized emails received since the given timestamp."""

    @abstractmethod
    def archive(self, provider_message_id: str) -> None:
        """Archive a single email (never a permanent delete)."""

    @abstractmethod
    def restore(self, provider_message_id: str) -> None:
        """Restore a previously archived email."""
