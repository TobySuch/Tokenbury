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
| `API_HIDE_FUTURE_TICKS` | No | `false` | When `true`, the tick API hides ticks whose in-game time is still in the future |
| `LOG_LEVEL` | No | `INFO` | Logging verbosity |
| `WEREWOLF_LLM_MODEL` | No | `anthropic/claude-haiku-5.5` | Model used by the werewolf game (players and moderator) |
| `WEREWOLF_RUN_HOUR` | No | `0` | Hour (UTC) after which `run_day --if-due` plays the day's run |

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
| `CSRF_TRUSTED_ORIGINS` | No | Comma-separated origins trusted for CSRF (e.g. `https://yourdomain.com`), needed for admin logins over HTTPS behind the proxy |
| `LLM_MODEL` | No | Town simulation model. Default `anthropic/claude-haiku-4-5` |
| `TICK_INTERVAL_MINUTES` | No | In-game minutes per tick. Default `15` |
| `PLAN_HOUR` | No | In-game hour for daily plans. Default `6` |
| `API_HIDE_FUTURE_TICKS` | No | `true` hides ticks whose in-game time is in the future. Default `false` |
| `LOG_LEVEL` | No | Default `INFO` |
| `COMPOSE_PROFILES` | No | Optional services to run: `ticker` (town auto-ticker), `werewolf` (daily werewolf runner), or `ticker,werewolf` |
| `TICKER_POLL_INTERVAL_MINUTES` | No | How often the ticker service checks for a due tick. Default `5` |
| `WEREWOLF_LLM_MODEL` | No | Werewolf game model. Default `anthropic/claude-haiku-5.5` |
| `WEREWOLF_RUN_HOUR` | No | Hour (UTC) after which the werewolf runner plays each day. Default `0` (midnight) |
| `WEREWOLF_POLL_INTERVAL_MINUTES` | No | How often the werewolf runner checks whether a day is due. Default `15` |
| `PLAUSIBLE_DOMAIN`, `PLAUSIBLE_URL` | No | Read by Caddy when serving `index.html`. If both are set, the Plausible script `${PLAUSIBLE_URL}/js/script.js` is added for `PLAUSIBLE_DOMAIN`. Set them on the `caddy` service |

### HTTPS

Caddy handles TLS automatically via Let's Encrypt when `ALLOWED_HOSTS` is set to a real domain. Update the `Caddyfile` host from `:80` to your domain name, and ensure ports 80 and 443 are open.

---

## Werewolf

A separate game in which the AI characters play Werewolf, watchable at `/werewolf`. The rules and design are in [`werewolf-spec.md`](./werewolf-spec.md).

### Running a game

1. Seed the cast once: `cd backend && uv run python manage.py seed_werewolf_characters`. In production, run it in the `backend` container so avatars are copied into the media volume.
2. Create a game in the admin (Werewolf → Games → Add) or with `make werewolf-game ARGS="--seed 7"`. New games start **unpublished**, so they are hidden from the site and skipped by the scheduler.
3. Optionally play a day by hand to check it: `make werewolf-day ARGS="--game <id>"`. Add `--scripted` to use canned actions with no LLM calls.
4. Tick **Published** on the game in the admin, or pass `--publish` when creating it.
5. To play one day per day automatically, enable the `werewolf` Compose profile. Each day after `WEREWOLF_RUN_HOUR` (UTC), it plays one night and day of **every** published active game, one after another, so several games can run side by side.

To start another game once one has finished, create and publish a new one, e.g. in production: `docker compose exec backend uv run python manage.py create_werewolf_game --publish`. The site shows a tab for each published game and opens on the newest.

### Game settings

Set per game when it's created (the admin form's settings JSON, or `--config key=value`), and read-only afterwards. Any key left out uses its default.

| Setting | Default | Description |
|---|---|---|
| `player_count` | `7` | Number of players, 5–12 |
| `wolf_count` | `null` (auto) | Wolves. Auto is about one per 3.5 players |
| `seer_count` | `null` (auto) | 0 or 1. Auto is 1 |
| `doctor_count` | `null` (auto) | 0 or 1. Auto is 1 from 6 players |
| `lovers` | `true` | Secretly link two players (never two wolves) as lovers |
| `lovers_chat_max_messages` | `4` | Messages in the lovers' nightly private chat |
| `reveal_role_on_death` | `true` | Announce a player's role when they die |
| `votes_public` | `true` | The vote result shows who voted for whom (otherwise counts only) |
| `wolf_chat_max_messages` | `6` | Wolf chat turns per night before the engine picks the kill |
| `discussion_min_messages` | `6` | Messages before the moderator may end the discussion |
| `discussion_max_messages` | `30` | Hard cap on messages in a day's discussion |
| `discussion_max_per_player` | `6` | Messages per player per discussion |
| `max_days` | `8` | Days before the game ends in a draw |
| `speech_max_chars` | `400` | Maximum length of one message |
| `notes_max_chars` | `3000` | Maximum size of a player's private notes |
| `max_note_calls_per_turn` | `4` | Note edits allowed in one turn |
| `call_budget` | `500` | Maximum LLM calls for the whole game (players and moderator, including retries). Reaching it aborts the game |
| `call_timeout_seconds` | `60` | Timeout for each LLM call; a timed-out turn falls back to pass, or to voting for no one |

---

## Other Commands

```bash
make migrate          # run migrations
make makemigrations   # create new migrations
make migrations       # makemigrations + migrate in one go
make shell            # Django shell
make createsuperuser  # create a Django admin user
make ticker           # run the simulation ticker
make werewolf-game    # create a werewolf game (ARGS="--seed 7 --publish")
make werewolf-day     # play the next werewolf day (ARGS="--game <id> [--scripted] [--until-over]")
make format           # format Python + frontend code
make lint             # lint frontend and backend
make test             # run all tests
```

---

## Project Structure

See [`CLAUDE.md`](./CLAUDE.md) for full project context, architecture decisions, and data models.
