# Framegrab Tagger

Framegrab Tagger is a web-based system for ingesting movie still images, predicting their source films, and enriching them with trusted metadata. The project uses FastAPI for the backend, Postgres for storage, Redis/Celery for asynchronous tasks, and supports pluggable metadata providers (TMDb/OMDb/IMDb where licensed).

## Status

This repository is currently in the scaffolding phase. The initial backend service is included with a small set of placeholder endpoints and testing harness to support incremental development of the pipelines described in the project brief.

## Quick start (backend + workers)

### Prerequisites

- Python 3.11+
- (Optional) Docker for running Postgres, Redis, and MinIO via `docker-compose`

### Setup

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

#### Environment variables

The backend ships with Celery tasks, S3-compatible storage access, and a TMDb client. Configure services via environment variables (or a `.env` file):

- `APP_DATABASE_URL` / `DATABASE_URL` (default `postgresql+psycopg://movietag:movietag@localhost:5432/movietag`)
- `APP_CELERY_BROKER_URL` / `CELERY_BROKER_URL` (default `redis://localhost:6379/0`)
- `APP_CELERY_RESULT_BACKEND` / `CELERY_RESULT_BACKEND` (default `redis://localhost:6379/1`)
- `APP_CELERY_DEFAULT_QUEUE` / `CELERY_DEFAULT_QUEUE` (default `movietag.default`)
- `APP_TMDB_API_KEY` / `TMDB_API_KEY` (Bearer token for TMDb)
- `APP_TMDB_BASE_URL` / `TMDB_BASE_URL` (default `https://api.themoviedb.org/3`)
- `APP_STORAGE_ENDPOINT_URL` / `STORAGE_ENDPOINT_URL` (e.g., `http://localhost:9000` for MinIO)
- `APP_STORAGE_ACCESS_KEY` / `STORAGE_ACCESS_KEY`
- `APP_STORAGE_SECRET_KEY` / `STORAGE_SECRET_KEY`
- `APP_STORAGE_FRAMES_BUCKET` / `STORAGE_FRAMES_BUCKET` (default `frames`)

Celery tasks are defined under `app/tasks`, and the default worker app is created in `app/core/celery.py`.

### Run the API

```bash
cd backend
uvicorn app.main:app --reload
```

Run the Celery worker in a second terminal:

```bash
cd backend
celery -A app.core.celery.celery_app worker --loglevel=info
```

The API serves under `http://localhost:8000/api`. Visit `http://localhost:8000/docs` for the automatically generated OpenAPI docs.

### Run database migrations

Apply the initial schema to your database using Alembic. Set `APP_DATABASE_URL` (or the conventional `DATABASE_URL`) in a `.env` file or environment variable to point at your Postgres instance if you are not using the default connection string:

```bash
cd backend
alembic upgrade head
```

### Run tests

```bash
cd backend
pytest
```

### Run dependencies with Docker

The repository includes a `docker-compose.yml` file that provisions Postgres, Redis, MinIO, the FastAPI API, and a Celery worker for local development:

```bash
docker-compose up -d
```

You can tear everything down with:

```bash
docker-compose down -v
```

## Services

- FastAPI API (`/api/frames`, `/api/movies`, `/api/health`)
- Celery worker processing ingestion, tagging, TMDb enrichment, and scene/actor detectors
- Postgres, Redis, MinIO for persistence and queues
- Kubernetes manifests are available under `deploy/k8s/movietag.yaml` for clustered deployments with API + worker deployments and backing services.

## Task + ingest overview

- `POST /api/frames/ingest` or `/api/frames/ingest/upload` queues the full pipeline (`frames.pipeline`) that imports, embeds, tags, annotates scene attributes, and detects actors.
- `GET /api/frames` lists frames with filters (movie id, tag, status, cast member, time of day) plus pagination and sorting.
- `POST /api/movies/ingest` enqueues TMDb metadata enrichment (`tmdb.ingest_movie`) to populate movies, cast, and artwork.

## Next steps

- Plug in production-grade embedding and detection models (CLIP, face recognition) behind the Celery tasks.
- Add auth and RBAC for moderation endpoints.
- Serve signed URLs from MinIO/S3 for browser-safe frame previews.

## Frontend (Next.js)

The `frontend` directory contains a React/Next.js interface for browsing frames, reviewing predictions, and applying overrides.

```bash
cd frontend
npm install
npm run dev
```

Key views:

- Frame grid with filtering by search and review status.
- Detail sidebar that shows per-frame predictions, status, and metadata.
- Override form to approve a model prediction or submit a manual correction.

## Current API surface

- `GET /api/health`: readiness probe returning the current environment and version.
- `GET /`: friendly root response with a link to the OpenAPI docs.
