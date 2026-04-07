# Scholarly Aether Backend (FastAPI)

## Stack
- FastAPI + SQLAlchemy
- Postgres
- JWT auth (password-based)
- Firecrawl for crawling
- Local LLM (LM Studio) for summarization (OpenAI-compatible endpoint)
- fpdf2 for PDF generation
- Redis + RQ worker for background crawling

## Setup
1) Create a virtualenv and install deps:
```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```
2) Copy .env.example to .env and fill values (secret key, Postgres URL, Firecrawl key, LLM base URL/model).
3) Run the app:
```
uvicorn app.main:app --reload
python worker.py  # separate terminal for RQ worker
```

### Docker (API + Worker + Postgres + Redis + Directus)
```
docker compose up --build
```
- API: http://localhost:8000
- Directus (headless CMS UI): http://localhost:8055
- Postgres: localhost:5432
- Redis: localhost:6379

## Postgres quickstart
```
psql -U postgres -c "CREATE DATABASE ai_research;"
```

## Auth flow
- POST /auth/register {email, password}
- POST /auth/token (OAuth2 Password Grant) → access_token
- Include `Authorization: Bearer <token>` on subsequent calls.

## Crawl + summarize flow
- POST /crawl {url} → enqueues RQ job: Firecrawl markdown → LLM summary → PDF
- GET /crawl/{job_id} → job state
- GET /documents → list user documents

## Directus (optional headless CMS)
If you want a UI for content editing, Directus runs in docker-compose. It manages curated content/taxonomy; FastAPI handles auth + crawl/summarize.

## Migrations
Alembic is configured.
```
alembic revision --autogenerate -m "init"
alembic upgrade head
```

## Frontend wiring
- Auth: use /auth/register then /auth/token to obtain Bearer token; store in local storage/session as you prefer.
- Crawl: POST /crawl with Authorization header, then poll GET /crawl/{job_id}. When status is completed, use GET /documents to render summaries/PDF links.
- Directus: log in at http://localhost:8055 with admin email/password from .env to manage CMS collections.
