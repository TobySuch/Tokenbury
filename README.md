# Tokenbury-on-Sea 🌊

A living, watchable AI simulation of a sleepy English coastal village. A cast of AI agents go about their daily lives — drinking at the pub, arguing on the beach, falling out over recycling — while the public watches in real time.

Inspired by [Generative Agents: Interactive Simulacra of Human Behavior](https://arxiv.org/abs/2304.03442) (Park et al., 2023). Truman Show vibes.

---

## Stack

- **Backend** — Python 3.14, Django, Django REST Framework, Django Channels
- **Frontend** — React, Vite, Tailwind CSS, Zustand
- **LLM** — Any LLM on OpenRouter
- **Database** — SQLite (development), Postgres (production)

---

## Development

### Prerequisites

- [uv](https://github.com/astral-sh/uv) (Python package manager)
- [bun](https://bun.sh) (JavaScript runtime)

### Setup

```bash
git clone <repo>
cd tokenbury
make install
```

Copy the env file and add your OpenRouter API key:

```bash
cp .env.example .env
# edit .env and set OPENROUTER_API_KEY
```

Get an API key at [openrouter.ai/keys](https://openrouter.ai/keys).

### Run

```bash
make dev
```

Starts the Django backend on `:8000` and the Vite frontend on `:5173`. Vite proxies `/api/*` to Django so you only need to open `http://localhost:5173`.

### Dev environment variables (`backend/.env`)

| Variable | Required | Default | Description |
|---|---|---|---|
| `OPENROUTER_API_KEY` | Yes | — | Your OpenRouter API key |
| `LLM_MODEL` | No | `anthropic/claude-haiku-4-5` | Model to use for agent generation |
| `TICK_INTERVAL_MINUTES` | No | `15` | How many minutes of in-game time each tick advances |
| `PLAN_HOUR` | No | `6` | In-game hour when agents form their daily plan |
| `LOG_LEVEL` | No | `INFO` | Logging verbosity |

---

## Production

Production runs via Docker Compose: Postgres for the database, Django + uvicorn for the backend, and Caddy as the reverse proxy serving the built React frontend.

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) with the Compose plugin

### Setup

```bash
cp .env.example .env
# edit .env and fill in all required values (SECRET_KEY, POSTGRES_PASSWORD, etc.)
```

Then start everything:

```bash
make prod
```

The app will be available on port 80. To stop:

```bash
make prod-down
```

### Production environment variables (`.env`)

| Variable | Required | Description |
|---|---|---|
| `SECRET_KEY` | Yes | Django secret key — generate with `python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"` |
| `OPENROUTER_API_KEY` | Yes | Your OpenRouter API key |
| `ALLOWED_HOSTS` | Yes | Comma-separated list of domains Django will accept (e.g. `yourdomain.com`) |
| `POSTGRES_DB` | Yes | Postgres database name (e.g. `tokenbury`) |
| `POSTGRES_USER` | Yes | Postgres user (e.g. `tokenbury`) |
| `POSTGRES_PASSWORD` | Yes | Postgres password |
| `DATABASE` | Yes | Must be `postgres` for production |
| `SQL_HOST` | Yes | Database host — use `db` when running via Docker Compose |
| `SQL_PORT` | Yes | Database port — `5432` |
| `SQL_DATABASE` | Yes | Must match `POSTGRES_DB` |
| `SQL_USER` | Yes | Must match `POSTGRES_USER` |
| `SQL_PASSWORD` | Yes | Must match `POSTGRES_PASSWORD` |
| `CORS_ALLOWED_ORIGINS` | No | Comma-separated CORS origins if frontend is on a different domain |
| `LLM_MODEL` | No | `anthropic/claude-haiku-4-5` |
| `TICK_INTERVAL_MINUTES` | No | `15` |
| `LOG_LEVEL` | No | `INFO` |

### HTTPS

Caddy handles TLS automatically via Let's Encrypt when `ALLOWED_HOSTS` is set to a real domain. Update the `Caddyfile` host from `:80` to your domain name, and ensure ports 80 and 443 are open.

---

## Other Commands

```bash
make migrate          # run migrations
make makemigrations   # create new migrations
make migrations       # makemigrations + migrate in one go
make shell            # Django shell
make createsuperuser  # create a Django admin user
make ticker           # run the simulation ticker
make format           # format Python + frontend code
make lint             # lint frontend and backend
make test             # run all tests
```

---

## Project Structure

See [`CLAUDE.md`](./CLAUDE.md) for full project context, architecture decisions, and data models.
