# Inbox Relief & Intelligence System

Self-hosted, privacy-preserving AI email assistant. Two jobs: archive old/low-value
mail (never deletes), and daily triage of what needs attention, with visible
reasoning. Classification runs on a local LLM (Ollama) — email content never goes
to a third-party cloud AI provider.

Full spec lives in the docs site (project charter, architecture, module guide,
roadmap, security/POPIA notes) — not included in this repo.

## Status

Gmail ingestion, Postgres persistence, and RAG retrieval all proven
end-to-end: ~2,000 real emails synced, embedded, and semantically searchable.
No second provider (Outlook skipped for now — see project notes), no
classification/archival logic yet, no frontend — see `backend/app/main.py`.

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

If you're behind a corporate proxy/antivirus that does TLS inspection, you may
hit `SSLCertVerificationError: self-signed certificate in certificate chain`.
This is already handled — `truststore.inject_into_ssl()` in
`app/providers/gmail.py` makes Python trust the Windows certificate store
instead of the bundled CA list.

## Repo layout

```
backend/
  app/
    providers/
      base.py        # MailProvider interface + NormalizedEmail shape
      gmail.py        # Gmail adapter (OAuth, fetch, archive/restore)
    config.py
    db.py             # SQLAlchemy async engine/session
    models.py         # Tenant, User, Email ORM models
    embeddings.py      # Ollama embedding calls
    vectorstore.py      # Qdrant collection per tenant
    main.py            # FastAPI app
  scripts/
    authorize_gmail.py
  secrets/          # git-ignored — credentials.json, token.json live here
```
