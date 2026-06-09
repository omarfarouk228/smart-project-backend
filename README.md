# SmartTask — Backend

FastAPI backend for SmartTask. Single-tenant, feature-first architecture.

## Stack

- **FastAPI** — async REST API + WebSockets
- **PostgreSQL 16** — primary database
- **Redis 7** — WebSocket pub/sub (real-time board events)
- **SQLAlchemy 2 (async)** — ORM with asyncpg driver
- **Alembic** — database migrations
- **python-jose** — JWT (access + refresh tokens)
- **passlib[bcrypt]** — password hashing
- **aiosmtplib + Jinja2** — transactional email

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # edit at minimum SECRET_KEY
docker compose up db redis -d
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

## Project structure

```
app/
  core/
    config.py        — Pydantic Settings (reads .env)
    database.py      — async engine, AsyncSession, Base
    security.py      — JWT, password hashing, token generation
    dependencies.py  — get_current_user, require_permissions
    middleware.py    — SetupMiddleware (503 until setup complete)
    redis.py         — async Redis client
    state.py         — in-memory AppState singleton

  features/
    setup/           — one-time wizard (seeds permissions, admin, org)
    auth/            — login, refresh, logout, change-password
    organization/    — branding, SMTP, logo upload
    users/           — CRUD, avatar, password reset
    roles/           — permissions, roles, user role assignments
    projects/        — project CRUD, columns, members
    tasks/           — tasks, subtasks, comments, labels, move endpoint
    sprints/         — sprint lifecycle, backlog, sprint board
    websockets/      — WS endpoint + Redis pub/sub forwarding

  main.py            — FastAPI app, CORS, middleware, router registration
```

## Authentication

- Email/password login → `access_token` (15 min) + `refresh_token` (7 days)
- Refresh tokens are stored hashed (SHA-256) in the DB; rotation on each refresh
- `Authorization: Bearer <access_token>` header on all protected routes
- WebSocket auth via `?token=<access_token>` query param

## RBAC

- Permissions have `codename` strings: `projects.create`, `users.manage`, etc.
- Roles aggregate permissions; users can have multiple roles
- `is_superadmin = True` bypasses all permission checks
- 15 permissions seeded across 5 categories on first setup

## Real-time (WebSockets)

```
WS /api/ws/{project_id}?token={access_token}
```

Events pushed to clients:
- `task:created` — full task payload
- `task:updated` — full task payload
- `task:moved`   — `{task_id, column_id, position}`
- `task:deleted` — `{task_id}`

When a task mutation happens via REST API, the service publishes to Redis channel `project:{id}`. The WS handler subscribes to that channel and forwards messages to all connected clients for that project.

## Running migrations

```bash
# Auto-generate from model changes
alembic revision --autogenerate -m "your description"

# Apply
alembic upgrade head

# Rollback one step
alembic downgrade -1
```

## Environment variables

See `.env.example` for all variables. Minimum required: `SECRET_KEY`, `DATABASE_URL`.
