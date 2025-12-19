# Framegrab Tagger

Framegrab Tagger is a web-based system for ingesting movie still images, predicting their source films, and enriching them with trusted metadata. The project uses FastAPI for the backend, Postgres for storage, Redis/Celery for asynchronous tasks, and supports pluggable metadata providers (TMDb/OMDb/IMDb where licensed).

## Status

This repository is currently in the scaffolding phase. The initial backend service is included with a small set of placeholder endpoints and testing harness to support incremental development of the pipelines described in the project brief.

## Quick start (backend only)

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

The backend now ships with Celery scaffolding and a TMDb client. Configure these services via environment variables (or a `.env` file):

- `APP_CELERY_BROKER_URL` / `CELERY_BROKER_URL` (default `redis://localhost:6379/0`)
- `APP_CELERY_RESULT_BACKEND` / `CELERY_RESULT_BACKEND` (default `redis://localhost:6379/1`)
- `APP_CELERY_DEFAULT_QUEUE` / `CELERY_DEFAULT_QUEUE` (default `movietag.default`)
- `APP_TMDB_API_KEY` / `TMDB_API_KEY` (Bearer token for TMDb)
- `APP_TMDB_BASE_URL` / `TMDB_BASE_URL` (default `https://api.themoviedb.org/3`)

Celery tasks are defined under `app/tasks`, and the default worker app is created in `app/core/celery.py`.

### Run the API

```bash
cd backend
uvicorn app.main:app --reload
```

The API will serve under `http://localhost:8000/api`. Visit `http://localhost:8000/docs` for the automatically generated OpenAPI docs.

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

The repository includes a `docker-compose.yml` file that provisions Postgres, Redis, and MinIO for local development:

```bash
docker-compose up -d
```

You can tear everything down with:

```bash
docker-compose down -v
```

## Services

`docker-compose.yml` includes Postgres, Redis, and MinIO for local development. The FastAPI backend is intended to run on your host or inside a container that mounts the source tree.

## Next steps

- Bring up a Celery worker process (e.g., `celery -A app.core.celery:celery_app worker --loglevel=info`) and wire the task stubs to real ingestion, embedding, and tagging logic.
- Expand the TMDb integration to persist movies, cast, and artwork into the database.
- Finalize Alembic migrations for the current schema and future changes as new entities are introduced.
- Add the React/Next.js frontend for browsing frames, reviewing predictions, and applying overrides.

## Current API surface

- `GET /api/health`: readiness probe returning the current environment and version.
- `GET /`: friendly root response with a link to the OpenAPI docs.
