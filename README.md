# Inbox Relief & Intelligence System

Self-hosted, privacy-preserving AI email assistant. Two jobs: archive old/low-value
mail (never deletes), and daily triage of what needs attention, with visible
reasoning. Classification runs on a local LLM (Ollama) — email content never goes
to a third-party cloud AI provider.

Full spec lives in the docs site (project charter, architecture, module guide,
roadmap, security/POPIA notes) — not included in this repo.

## Status

Backend is functionally complete for the MVP loop: Gmail ingestion → Postgres
persistence → RAG retrieval (Qdrant) → LLM classification (urgency +
archive-worthiness) → real archive/restore execution → corrections/rules
feedback loop → unified chat (question/rule/correction intent) → daily
digest. All proven end-to-end against ~2,000 real emails from a live Gmail
account. No second provider (Outlook skipped for now — see project notes).

Frontend (React + TS + Tailwind) now exists with four views — Digest, Inbox,
Chat, Rules — talking to the backend via a Vite dev proxy. Custom warm/editorial
palette (navy/rust/cream), not the default framework look.

Outlook is intentionally not implemented yet: the `MailProvider` interface
supports adding it later as a bounded, additive piece of work whenever a
usable Microsoft account is available (school tenants often block app
registration for students).

## Backend setup

```
cd backend
python -m venv venv
venv\Scripts\activate        # or: source venv/Scripts/activate (git bash)
pip install -r requirements.txt
```

Copy `.env.example` to `.env` (already done in dev). Put your downloaded Google
Cloud OAuth client JSON at `backend/secrets/credentials.json` (git-ignored, never
commit this).

First-time Gmail authorization (opens a browser consent screen):

```
python scripts/authorize_gmail.py
```

### Postgres (dev)

Runs on host port **5433** (not 5432) to avoid clashing with other local
Postgres containers:

```
docker run --name inbox-relief-pg -e POSTGRES_PASSWORD=devpassword -e POSTGRES_DB=inbox_relief -p 5433:5432 -d postgres:16
```

Tables are created automatically on API startup (`app/db.py: init_models`) —
no manual migration step yet (fine for MVP; revisit with Alembic if the schema
needs to evolve without dropping data).

### Qdrant + Ollama (dev)

Qdrant runs on non-default ports to avoid clashing with other local containers:

```
docker run --name inbox-relief-qdrant -p 6335:6333 -p 6336:6334 -d qdrant/qdrant
```

Ollama runs natively (not in Docker) and serves the local models used for
embeddings and (later) classification:

```
ollama pull nomic-embed-text
ollama pull llama3.1:8b
```

### Running the API

```
uvicorn app.main:app --reload
```

- `GET /ingest/gmail/sync?limit=200` — fetch Gmail messages (paginated) and upsert into Postgres.
  `limit` caps how many are fetched; omit/set high for a full historical sync (slow — expect
  roughly 300ms/email just for ingestion on a large mailbox, so size the limit accordingly)
- `GET /emails` — list stored emails
- `GET /index/gmail` — embed any stored emails not yet embedded and upsert into Qdrant
- `GET /search?q=...` — semantic search over embedded emails (proves RAG retrieval)
- `GET /classify/gmail?limit=20` — judge urgency + archive-worthiness via local LLM + RAG
  (rules are checked first and skip the LLM when matched); bounded by default, CPU inference
  is slow (~10-25s/email for llama3.1:8b). Processes newest-unclassified-first. Anything judged
  `should_archive` at confidence ≥ `AUTO_ARCHIVE_CONFIDENCE_THRESHOLD` (0.85) is archived
  immediately — this is the confidence gate: only near-certain low-value mail auto-archives,
  everything else waits for a human decision via `/archive/candidates` + `/archive/auto` or
  the UI
- `GET /emails/classified` — list classified emails with their judgments
- `POST /emails/{id}/archive`, `POST /emails/{id}/restore` — real Gmail label changes
  (archive is never a permanent delete)
- `GET /archive/candidates?threshold=0.7` — preview what auto-archive would do, no side effects
- `POST /archive/auto?threshold=0.7` — actually execute bulk archive for high-confidence candidates
- `POST /emails/{id}/correct` — record a correction (`field`: `should_archive`|`urgency`,
  `corrected_value`, optional `note`); reverses an archive if applicable
- `GET /digest` — mailbox stats + emails needing attention **received today** (unarchived,
  medium/high urgency) — deliberately date-scoped, not an ever-growing backlog
- `GET /calendar?year&month` — per-day received/archived/unread/high-urgency counts
- `GET /calendar/day?date=YYYY-MM-DD` — full email list for one day (calendar drill-down)
- `POST /chat` — free-text message (`message`, optional `email_id`); classifies intent as
  correction/rule/question and acts accordingly (rules feed back into `/classify/gmail`)
- `GET /rules` — list standing rules; `POST /rules` — create one from structured fields;
  `POST /rules/from_text` — create one from plain language (e.g. "emails from Acme are not
  important, archive them") using the same LLM extraction chat uses, stores the original text
  as `source_text` for display; `DELETE /rules/{id}` — remove one (now audit-logged)
- `GET /senders/never-replied?min_count=2` — senders where you've never sent a message in any
  of their threads (learned from actual reply history, not guessed): a strong signal for
  bulk-archivable promotional/notification mail. `POST /senders/never-replied/apply` —
  bulk-create archive rules for chosen senders (reviewable, not automatic — the caller picks
  which suggestions to apply)
- `GET /storage` — real Gmail/Drive/Photos storage quota (used/limit/percent), via Drive's
  `about.get` since the Gmail API itself has no way to read it. Requires the `drive.readonly`
  scope (added alongside `gmail.modify`) and Drive API enabled in the Cloud Console project.
  Purely informational — never changes when we archive, since archiving only removes the
  Inbox label and Gmail counts Inbox + Archive + Trash identically toward quota

Classification also attempts to extract an explicit deadline/due date (assessment due dates,
submission deadlines, etc.) into `due_date`, resolving relative phrases ("due Friday") against
the email's received date. Caveat: small local LLMs are weak at relative-date arithmetic — in
testing it correctly detected a deadline but resolved "this Friday" two days off. Treat it as a
helpful hint to verify, not a guaranteed-accurate calendar.

Note: resetting `classified_at` to force reclassification does NOT clear the old
`should_archive`/`confidence`/`urgency`/`reasoning` values — clear those explicitly too, or the
archive-candidate queries will act on stale judgments (a real bug caught during testing).

If you're behind a corporate proxy/antivirus that does TLS inspection, you may
hit `SSLCertVerificationError: self-signed certificate in certificate chain`.
This is already handled — `truststore.inject_into_ssl()` in
`app/providers/gmail.py` makes Python trust the Windows certificate store
instead of the bundled CA list.

Chat uses a separate, smaller/faster model (`CHAT_MODEL`, default
`llama3.2:3b`) than classification (`INFERENCE_MODEL`, `llama3.1:8b`) — chat
latency matters more than raw accuracy there, while archive decisions warrant
the larger model. `/chat` does intent classification + the intent's payload
(answer/rule) in a single LLM call, not two.

## Frontend setup

```
cd frontend
npm install
npm run dev
```

Runs on `http://localhost:5173`, proxying `/api/*` to the backend on port 8000
(see `vite.config.ts`) — no CORS setup needed, run both dev servers side by side.

Five views: **Digest** (today's stats + emails needing attention today), **Inbox**
(browse/search/filter by urgency/archive/restore all classified mail), **Calendar** (per-day
counts, click any day or a specific stat like "high"/"unread"/"archived" to drill into that
exact list), **Chat**, **Rules** (write one in plain language, or use the manual form).

Every email has a "Read email" expander (fetches full content on demand) plus a "Reply in
Gmail" button using a reliable RFC822 Message-ID search deep link — not Gmail's internal
message ID, which doesn't reliably deep-link since Gmail's web UI is thread-centric. This app
stays read-only; replying happens in Gmail itself, and Gmail has no officially reliable way to
deep-link straight into reply/compose mode, so we don't pretend otherwise.

## Repo layout

```
backend/
  app/
    providers/
      base.py        # MailProvider interface + NormalizedEmail shape
      gmail.py        # Gmail adapter (OAuth, fetch, archive/restore — needs gmail.modify scope)
    config.py
    db.py             # SQLAlchemy async engine/session
    models.py         # Tenant, User, Email, Correction, AuditLog, Rule ORM models
    embeddings.py      # Ollama embedding calls
    vectorstore.py      # Qdrant collection per tenant
    inference.py        # LLM classification (urgency, archive-worthiness) via RAG
    chat.py              # Unified chat: intent classification + rule extraction + Q&A
    main.py            # FastAPI app — all endpoints
  scripts/
    authorize_gmail.py
  secrets/          # git-ignored — credentials.json, token.json live here
frontend/
  src/
    api.ts               # typed fetch client + gmailLink() deep-link helper
    App.tsx              # view switcher (digest/inbox/calendar/chat/rules)
    components/
      Shell.tsx           # sidebar nav + layout
      DigestView.tsx        # today's stats + emails needing attention today
      InboxView.tsx          # browse/filter (status + urgency)/archive/restore all classified mail
      CalendarView.tsx        # per-day counts, click a day or a stat to drill down
      DayDetailPanel.tsx       # calendar drill-down: full/filtered email list for one day
      ChatPanel.tsx             # chat UI
      RulesPanel.tsx             # write a rule in plain language, or use the manual form
      QuickRuleButton.tsx         # one-click "always archive this sender"
      SuggestedRules.tsx           # review + bulk-apply rules for never-replied senders
      EmailExpando.tsx              # in-app "Read email" + "Reply in Gmail" expander
      Badge.tsx, StatCard.tsx        # small shared UI pieces
```
