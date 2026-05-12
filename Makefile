.PHONY: dev backend frontend prod prod-down install migrate makemigrations shell createsuperuser lint format test ticker

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