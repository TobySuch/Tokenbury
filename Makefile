.PHONY: dev backend frontend prod prod-down prod-ticker install migrate makemigrations shell createsuperuser lint format test ticker prod-werewolf werewolf-game werewolf-day

# ─── Dev Servers ─────────────────────────────────────────────────────────────

dev:
	make -j2 backend frontend

backend:
	cd backend && uv run python manage.py runserver

frontend:
	cd frontend && bun run dev

# ─── Production (Docker) ─────────────────────────────────────────────────────

prod:
	docker compose up --build -d

prod-ticker:
	docker compose --profile ticker up --build -d

prod-werewolf:
	docker compose --profile werewolf up --build -d

prod-down:
	docker compose down

# ─── Dependencies ─────────────────────────────────────────────────────────────

install:
	cd backend && uv sync
	cd frontend && bun install

# ─── Database ─────────────────────────────────────────────────────────────────

migrate:
	cd backend && uv run python manage.py migrate

makemigrations:
	cd backend && uv run python manage.py makemigrations

migrations: makemigrations migrate

# ─── Django Utilities ─────────────────────────────────────────────────────────

shell:
	cd backend && uv run python manage.py shell

createsuperuser:
	cd backend && uv run python manage.py createsuperuser

# ─── Simulation ───────────────────────────────────────────────────────────────

ticker:
	cd backend && uv run python manage.py run_ticker $(ARGS)

# ─── Werewolf ─────────────────────────────────────────────────────────────────

werewolf-game:
	cd backend && uv run python manage.py create_werewolf_game $(ARGS)

werewolf-day:
	cd backend && uv run python manage.py run_day $(ARGS)

# ─── Code Quality ─────────────────────────────────────────────────────────────

lint:
	cd backend && uv run ruff check .
	cd frontend && bun run lint
	cd frontend && bun run format:check

format:
	cd backend && uv run ruff format .
	cd frontend && bun run format

# ─── Tests ────────────────────────────────────────────────────────────────────

test:
	cd backend && uv run pytest
	cd frontend && bun run test