# Phase 0: Foundation Implementation Plan

This plan details the implementation of **Phase 0** as described in the `agent-build-spec.md` document. The goal is to set up the repository structure, database schema, docker containers, and foundational FastAPI setup.

## User Review Required

> [!IMPORTANT]  
> Please review this plan to ensure it aligns with your expectations. Once approved, I will begin creating the directories and files.

## Open Questions

None at this time. The `agent-build-spec.md` is very explicit about the requirements. I will use `psycopg2-binary` for the database driver to maintain simplicity with Alembic and SQLModel, unless you have a strong preference for `asyncpg`.

## Proposed Changes

We will create the following files to establish the foundation of the project:

### Root Level
#### [NEW] `docker-compose.yml`
Will configure three services:
- `api` (FastAPI backend)
- `db` (Postgres 15)
- `frontend` (React + Vite skeleton)

### Backend
#### [NEW] `backend/Dockerfile`
Will contain system dependencies for WeasyPrint (`libpango-1.0-0`, `libpangocairo-1.0-0`, `libcairo2`, `libgdk-pixbuf2.0-0`, `libffi-dev`, `shared-mime-info`) and copy the Python application.
#### [NEW] `backend/requirements.txt`
Will pin required dependencies: `fastapi`, `uvicorn`, `sqlmodel`, `alembic`, `psycopg2-binary`, `pydantic`, `pydantic-settings`, `python-multipart`, and `pytest`.
#### [NEW] `backend/alembic.ini`
Alembic configuration file for database migrations.

### Backend Application (`backend/app/`)
#### [NEW] `backend/app/main.py`
FastAPI app entrypoint with CORS middleware (allowing `http://localhost:5173`) and a `GET /health` endpoint.
#### [NEW] `backend/app/core/config.py`
Settings via `pydantic-settings` to manage environment variables (like `DATABASE_URL`).
#### [NEW] `backend/app/core/db.py`
SQLModel engine and session dependency creation.
#### [NEW] `backend/app/models/schema.py`
Pydantic v2 schemas exactly as defined in §3 of the spec (`SourceEvidence`, `SecurityBaselineField`, `DeviceIdentity`, `NormalizedDeviceConfig`, `ComplianceRule`, `Finding`, `CorrectionExample`).
#### [NEW] `backend/app/models/tables.py`
SQLModel table definitions exactly mapping to the Postgres DDL provided in §4 of the spec (`Device`, `NormalizedField`, `ComplianceRule`, `Finding`, `Correction`).
#### [NEW] `backend/app/alembic/env.py` and `backend/app/alembic/versions/...`
Initial Alembic migration script to generate the 5 tables.

### Frontend
#### [NEW] `frontend/Dockerfile`
Basic Node/Vite Dockerfile to serve the frontend application.
#### [NEW] `frontend/package.json` & Scaffold
A minimal React + Vite + TypeScript frontend to allow `docker-compose up` to run successfully. (I will run `npm create vite@latest` for this).

## Verification Plan

### Automated Tests
- Once the structure is built, we will run `docker compose build` and `docker compose up -d`.
- We will test the `GET /health` endpoint using `curl` or PowerShell `Invoke-RestMethod`.
- We will execute `alembic upgrade head` from within the `api` container and connect to Postgres to verify the tables exist using `\dt`.
