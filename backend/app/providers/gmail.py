import base64
from datetime import datetime, timezone
from pathlib import Path

import truststore

truststore.inject_into_ssl()  # trust the Windows cert store — needed behind corporate TLS-inspecting proxies

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from app.providers.base import MailProvider, NormalizedEmail

# Read-only for now — this is all Day 1-2 ingestion needs. archive()/restore()
# below require the gmail.modify scope; bump SCOPES and re-run auth_script.py
# once the Archive & Feedback Service module is built.
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

ARCHIVED_LABEL_NAME = "Archived-By-System"


class GmailProvider(MailProvider):
    def __init__(self, credentials_path: str, token_path: str):
        self.credentials_path = Path(credentials_path)
        self.token_path = Path(token_path)
        self._service = None

    def authenticate(self) -> None:
        creds = None
        if self.token_path.exists():
            creds = Credentials.from_authorized_user_file(str(self.token_path), SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(self.credentials_path), SCOPES
                )
                creds = flow.run_local_server(port=0)
            self.token_path.write_text(creds.to_json())

        self._service = build("gmail", "v1", credentials=creds)

    def fetch_new_emails(
        self, since: datetime | None = None, max_results: int | None = None
    ) -> list[NormalizedEmail]:
        """Paginates through Gmail's message list. max_results=None fetches
        every message matching the query (can be slow/large on a full mailbox)."""
        if self._service is None:
            raise RuntimeError("call authenticate() before fetch_new_emails()")

        query = f"after:{int(since.timestamp())}" if since else ""
        message_refs = []
        page_token = None
        while True:
            page_size = 500 if max_results is None else min(500, max_results - len(message_refs))
            request = (
                self._service.users()
                .messages()
                .list(userId="me", q=query, maxResults=page_size, pageToken=page_token)
            )
            results = request.execute()
            message_refs.extend(results.get("messages", []))

            page_token = results.get("nextPageToken")
            if not page_token or (max_results is not None and len(message_refs) >= max_results):
                break

        emails: list[NormalizedEmail] = []
        for ref in message_refs:
            msg = (
                self._service.users()
                .messages()
                .get(userId="me", id=ref["id"], format="full")
                .execute()
            )
            emails.append(self._to_normalized_email(msg))
        return emails

    def archive(self, provider_message_id: str) -> None:
        """Requires gmail.modify scope — see SCOPES note above."""
        label_id = self._get_or_create_label_id(ARCHIVED_LABEL_NAME)
        self._service.users().messages().modify(
            userId="me",
            id=provider_message_id,
            body={"removeLabelIds": ["INBOX"], "addLabelIds": [label_id]},
        ).execute()

    def restore(self, provider_message_id: str) -> None:
        """Requires gmail.modify scope — see SCOPES note above."""
        label_id = self._get_or_create_label_id(ARCHIVED_LABEL_NAME)
        self._service.users().messages().modify(
            userId="me",
            id=provider_message_id,
            body={"removeLabelIds": [label_id], "addLabelIds": ["INBOX"]},
        ).execute()

    def _get_or_create_label_id(self, name: str) -> str:
        labels = self._service.users().labels().list(userId="me").execute().get("labels", [])
        for label in labels:
            if label["name"] == name:
                return label["id"]
        created = (
            self._service.users()
            .labels()
            .create(userId="me", body={"name": name})
            .execute()
        )
        return created["id"]

    @staticmethod
    def _to_normalized_email(msg: dict) -> NormalizedEmail:
        headers = {h["name"].lower(): h["value"] for h in msg["payload"].get("headers", [])}
        recipients = [r.strip() for r in headers.get("to", "").split(",") if r.strip()]
        received_at = datetime.fromtimestamp(int(msg["internalDate"]) / 1000, tz=timezone.utc)

        return NormalizedEmail(
            provider="gmail",
            provider_message_id=msg["id"],
            thread_id=msg["threadId"],
            subject=headers.get("subject", "(no subject)"),
            sender=headers.get("from", ""),
            recipients=recipients,
            received_at=received_at,
            snippet=msg.get("snippet", ""),
            body_text=GmailProvider._extract_body_text(msg["payload"]),
            labels=msg.get("labelIds", []),
            is_unread="UNREAD" in msg.get("labelIds", []),
        )

    @staticmethod
    def _extract_body_text(payload: dict) -> str:
        if payload.get("mimeType") == "text/plain" and "data" in payload.get("body", {}):
            return base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8", errors="replace")

        for part in payload.get("parts", []):
            text = GmailProvider._extract_body_text(part)
            if text:
                return text
        return ""
