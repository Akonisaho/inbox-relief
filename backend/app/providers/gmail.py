import base64
import time
from datetime import datetime, timezone
from pathlib import Path

import httplib2.error
import truststore

truststore.inject_into_ssl()  # trust the Windows cert store — needed behind corporate TLS-inspecting proxies

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from app.providers.base import MailProvider, NormalizedEmail

# gmail.modify covers both read and label-change access (archive/restore),
# short of permanent delete or account settings changes. drive.readonly is
# needed only for the storage-quota display (Gmail/Drive/Photos share one
# quota, exposed via Drive's `about.get`, not the Gmail API itself).
SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/drive.readonly",
]

ARCHIVED_LABEL_NAME = "Archived-By-System"


def _execute_with_retry(request, attempts: int = 6, base_delay: float = 3.0):
    """Long batches over a flaky connection occasionally hit a transient
    network failure mid-fetch — read timeouts (OSError) and full drops that
    surface as DNS resolution failures (httplib2's ServerNotFoundError, not
    an OSError subclass). Retry with backoff rather than aborting the whole
    sync over one blip; up to ~45s of cumulative backoff to ride out a short
    Wi-Fi/connection drop."""
    for attempt in range(1, attempts + 1):
        try:
            return request.execute()
        except (OSError, httplib2.error.HttpLib2Error):
            if attempt == attempts:
                raise
            time.sleep(base_delay * attempt)


class GmailProvider(MailProvider):
    def __init__(self, credentials_path: str, token_path: str):
        self.credentials_path = Path(credentials_path)
        self.token_path = Path(token_path)
        self._service = None
        self._drive_service = None
        self._creds = None
        self._archived_label_id = None

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

        self._creds = creds
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
            results = _execute_with_retry(request)
            message_refs.extend(results.get("messages", []))

            page_token = results.get("nextPageToken")
            if not page_token or (max_results is not None and len(message_refs) >= max_results):
                break

        emails: list[NormalizedEmail] = []
        for ref in message_refs:
            request = self._service.users().messages().get(userId="me", id=ref["id"], format="full")
            msg = _execute_with_retry(request)
            emails.append(self._to_normalized_email(msg))
        return emails

    def archive(self, provider_message_id: str) -> None:
        """Requires gmail.modify scope — see SCOPES note above."""
        label_id = self._get_or_create_label_id(ARCHIVED_LABEL_NAME)
        request = self._service.users().messages().modify(
            userId="me",
            id=provider_message_id,
            body={"removeLabelIds": ["INBOX"], "addLabelIds": [label_id]},
        )
        _execute_with_retry(request)

    def restore(self, provider_message_id: str) -> None:
        """Requires gmail.modify scope — see SCOPES note above."""
        label_id = self._get_or_create_label_id(ARCHIVED_LABEL_NAME)
        request = self._service.users().messages().modify(
            userId="me",
            id=provider_message_id,
            body={"removeLabelIds": [label_id], "addLabelIds": ["INBOX"]},
        )
        _execute_with_retry(request)

    def get_own_email_address(self) -> str:
        profile = _execute_with_retry(self._service.users().getProfile(userId="me"))
        return profile["emailAddress"]

    def get_storage_quota(self) -> dict:
        """Gmail/Drive/Photos share one storage quota — Gmail's own API has
        no way to read it, only Drive's `about.get` does. Requires the
        drive.readonly scope in addition to gmail.modify."""
        if self._drive_service is None:
            self._drive_service = build("drive", "v3", credentials=self._creds)
        about = _execute_with_retry(
            self._drive_service.about().get(fields="storageQuota")
        )
        quota = about["storageQuota"]
        used = int(quota.get("usage", 0))
        limit = int(quota["limit"]) if quota.get("limit") else None
        return {
            "used_bytes": used,
            "limit_bytes": limit,
            "percent_used": round(used / limit * 100, 1) if limit else None,
        }

    def _get_or_create_label_id(self, name: str) -> str:
        # Cached after first resolution — this used to hit the Gmail API fresh
        # on every single archive()/restore() call, which is both wasteful and
        # (since it wasn't retry-wrapped) a single point of failure for any
        # large batch: one transient network blip here used to abort the
        # entire caller, no matter how much progress it had already made.
        if self._archived_label_id is not None:
            return self._archived_label_id

        list_request = self._service.users().labels().list(userId="me")
        labels = _execute_with_retry(list_request).get("labels", [])
        for label in labels:
            if label["name"] == name:
                self._archived_label_id = label["id"]
                return self._archived_label_id

        create_request = (
            self._service.users().labels().create(userId="me", body={"name": name})
        )
        created = _execute_with_retry(create_request)
        self._archived_label_id = created["id"]
        return self._archived_label_id

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
            message_id_header=headers.get("message-id", ""),
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
