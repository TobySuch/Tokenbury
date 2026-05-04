.PHONY: dev backend frontend install migrate makemigrations shell createsuperuser lint format

# ─── Dev Servers ─────────────────────────────────────────────────────────────

dev:
	make -j2 backend frontend

backend:
	cd backend && uv run python manage.py runserver

frontend:
	cd frontend && bun run dev

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

# ─── Code Quality ─────────────────────────────────────────────────────────────

lint:
	cd backend && uv run ruff check .
	cd frontend && bun run lint

format:
	cd backend && uv run ruff format .