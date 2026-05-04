# Tokenbury-on-Sea 🌊

A living, watchable AI simulation of a sleepy English coastal village. A cast of AI agents go about their daily lives — drinking at the pub, arguing on the beach, falling out over recycling — while the public watches in real time.

Inspired by [Generative Agents: Interactive Simulacra of Human Behavior](https://arxiv.org/abs/2304.03442) (Park et al., 2023). Truman Show vibes.

---

## Stack

- **Backend** — Python 3.14, Django, Django REST Framework, Django Channels
- **Frontend** — React, Vite, Tailwind CSS, Zustand
- **LLM** — Claude Haiku via OpenRouter
- **Database** — SQLite (development) → Postgres (production)

## Getting Started

### Prerequisites

- [pyenv](https://github.com/pyenv/pyenv) with Python 3.14
- [uv](https://github.com/astral-sh/uv)
- [bun](https://bun.sh)

### Setup

```bash
git clone <repo>
cd tokenbury
make install
```

### Running

```bash
make dev
```

This starts both the Django backend on `:8000` and the Vite frontend on `:5173`.

## Other Commands

```bash
make migrate          # run migrations
make makemigrations   # create new migrations
make migrations       # makemigrations + migrate in one go
make shell            # Django shell
make createsuperuser  # create a Django admin user
make format           # format Python code with Ruff
make lint             # lint frontend and backend
```

## Project Structure

See [`CLAUDE.md`](./CLAUDE.md) for full project context, architecture decisions, and data models.
