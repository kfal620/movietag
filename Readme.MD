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

### Run the API

```bash
cd backend
uvicorn app.main:app --reload
```

The API will serve under `http://localhost:8000/api`. Visit `http://localhost:8000/docs` for the automatically generated OpenAPI docs.

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

- Implement database migrations (Alembic) covering the provided schema.
- Add Celery workers for import, embedding, and tagging tasks.
- Integrate TMDb as the first metadata provider and persist movie + cast records.
- Add the React/Next.js frontend for browsing, review, and overrides.

## Current API surface

- `GET /api/health`: readiness probe returning the current environment and version.
- `GET /`: friendly root response with a link to the OpenAPI docs.
