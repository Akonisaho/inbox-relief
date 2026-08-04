# Inbox Relief & Intelligence System

Self-hosted, privacy-preserving AI email assistant. Two jobs: archive old/low-value
mail (never deletes), and daily triage of what needs attention, with visible
reasoning. Classification runs on a local LLM (Ollama) — email content never goes
to a third-party cloud AI provider.

Full spec lives in the docs site (project charter, architecture, module guide,
roadmap, security/POPIA notes) — not included in this repo.

## Status

Day 1-2 of the build: Gmail ingestion proven end-to-end (auth + fetch). No
persistence, no second provider, no RAG, no frontend yet — see `backend/app/main.py`.

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

Run the dev API:

```
uvicorn app.main:app --reload
```

Then hit `http://127.0.0.1:8000/ingest/gmail/sync` to pull recent emails.

## Repo layout

```
backend/
  app/
    providers/
      base.py      # MailProvider interface + NormalizedEmail shape
      gmail.py      # Gmail adapter (OAuth, fetch, archive/restore)
    config.py
    main.py         # FastAPI app
  scripts/
    authorize_gmail.py
  secrets/          # git-ignored — credentials.json, token.json live here
```
