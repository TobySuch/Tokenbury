# Tokenbury-on-Sea 🌊

A living, watchable AI simulation of a sleepy English coastal village. A cast of AI agents go about their daily lives — drinking at the pub, arguing on the beach, falling out over recycling — while the public watches in real time.

Inspired by [Generative Agents: Interactive Simulacra of Human Behavior](https://arxiv.org/abs/2304.03442) (Park et al., 2023). Truman Show vibes.

---

## Stack

- **Backend** — Python 3.14, Django, Django REST Framework, Django Channels
- **Frontend** — React, Vite, Tailwind CSS, Zustand
- **LLM** — Any LLM on OpenRouter
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

Copy the example env file and add your OpenRouter API key:

```bash
cp backend/.env.example backend/.env
# then edit backend/.env and set OPENROUTER_API_KEY
```

Get an API key at [openrouter.ai/keys](https://openrouter.ai/keys).

### Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `OPENROUTER_API_KEY` | Yes | — | Your OpenRouter API key |
| `LLM_MODEL` | No | `anthropic/claude-haiku-4-5` | Model to use for agent generation |
| `TICK_INTERVAL_MINUTES` | No | `15` | How many minutes of in-game time each tick advances |

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
