"""Run once, standalone, to complete the Gmail OAuth consent flow and write
token.json. Opens a browser window; approve access for the test user account.

Usage (from backend/, with venv active):
    python scripts/authorize_gmail.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import GMAIL_CREDENTIALS_PATH, GMAIL_TOKEN_PATH
from app.providers.gmail import GmailProvider

if __name__ == "__main__":
    provider = GmailProvider(str(GMAIL_CREDENTIALS_PATH), str(GMAIL_TOKEN_PATH))
    provider.authenticate()
    print(f"Authorized. Token saved to {GMAIL_TOKEN_PATH}")

    emails = provider.fetch_new_emails(max_results=5)
    print(f"Fetched {len(emails)} recent emails:")
    for e in emails[:5]:
        line = f"  - [{e.received_at}] {e.subject!r} from {e.sender}"
        print(line.encode(sys.stdout.encoding or "utf-8", errors="replace").decode(sys.stdout.encoding or "utf-8"))
