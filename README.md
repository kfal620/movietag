# Framegrab Tagger

Framegrab Tagger is a web-based system for ingesting movie still images, predicting their source films, and enriching them with trusted metadata. It uses FastAPI for the backend, Celery for asynchronous pipelines, Postgres for storage, Redis for brokering tasks, and S3-compatible object storage for frames.

## Repository layout

- `backend/` – FastAPI application, Celery worker definitions, Alembic migrations, and pytest suites.
- `frontend/` – Next.js interface for browsing frames, reviewing predictions, and exporting results.
- `deploy/` – Kubernetes manifests.
- `docker-compose.yml` – Local stack for Postgres, Redis, MinIO, the API, and the worker.

## Backend quickstart

### Prerequisites

- Python 3.11+
- Postgres, Redis, and an S3-compatible store (MinIO works well locally)
- (Optional) TMDb and OMDb API keys for enrichment tasks

### Install dependencies

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
```

### Configure the environment

The backend reads environment variables (or a `.env` file) via `pydantic-settings`. Common options with defaults:

- `APP_DATABASE_URL` / `DATABASE_URL` (default `postgresql+psycopg://movietag:movietag@localhost:5432/movietag`)
- `APP_CELERY_BROKER_URL` / `CELERY_BROKER_URL` (default `redis://localhost:6379/0`)
- `APP_CELERY_RESULT_BACKEND` / `CELERY_RESULT_BACKEND` (default `redis://localhost:6379/1`)
- `APP_CELERY_DEFAULT_QUEUE` / `CELERY_DEFAULT_QUEUE` (default `movietag.default`)
- `APP_STORAGE_*` (`ENDPOINT_URL`, `ACCESS_KEY`, `SECRET_KEY`, `FRAMES_BUCKET`) for S3/MinIO access
- `APP_TMDB_API_KEY` / `APP_OMDB_API_KEY` for metadata providers
- `APP_ADMIN_TOKEN` / `APP_MODERATOR_TOKEN` bearer tokens for moderation-protected endpoints

### Run the API and worker

```bash
cd backend
uvicorn app.main:app --reload
# in another shell
celery -A app.core.celery.celery_app worker --loglevel=info
```

The API is served at `http://localhost:8000/api` with interactive docs at `/docs`. Ingest endpoints queue Celery pipelines for embedding, tagging, scene attribution, and actor detection.

### Apply database migrations

```bash
cd backend
alembic upgrade head
```

### Run tests

```bash
cd backend
pytest
```

## Local stack with Docker Compose

Bring up Postgres, Redis, MinIO, the API, and the worker in one command:

```bash
docker-compose up -d
```

Tear down everything (including volumes) with:

```bash
docker-compose down -v
```

## Frontend (Next.js)

The `frontend` app provides a frame grid, per-frame detail panel, override flows, and export tooling. It targets Node.js 18+.

```bash
cd frontend
npm install
npm run dev
```

The UI fetches data from `/api/...`, so run it behind a proxy that forwards `/api` to the FastAPI server (e.g., docker-compose or a local reverse proxy) to keep the browser origin consistent.
