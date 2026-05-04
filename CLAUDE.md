# Tokenbury-on-Sea — Claude Project Context

A living, watchable AI simulation of a sleepy English coastal town, inspired by the Stanford paper _Generative Agents: Interactive Simulacra of Human Behavior_ (Park et al., 2023). Think The Truman Show meets The Sims — a cast of AI agents living out their daily lives while the public watches in real time.

---

## The Concept

AI agents live in Tokenbury-on-Sea with personalities, beliefs, relationships, memories, and daily routines. They can deviate, argue, fall out, make plans, and surprise you. The public watches. They dip in, catch up on what they missed, get attached to characters.

---

## Key Design Principles

- **Append-only data model throughout** — no mutable world state snapshots. History and time travel emerge implicitly from the tables.
- **Single global simulation instance** — viewer count doesn't affect LLM cost.
- **Start with the smallest working loop** — resist the pull to architect everything upfront.
- **Agents make isolated per-agent LLM calls** — no cross-agent leakage in prompts.
- **Configurable tick system** — default one real-world hour = one in-game hour.

---

## Tech Stack

| Layer              | Tech                                                  |
| ------------------ | ----------------------------------------------------- |
| Backend            | Python 3.14, Django, Django REST Framework            |
| WebSockets         | Django Channels                                       |
| Task queue         | Celery or Django Q (deferred)                         |
| Database           | SQLite → Postgres when going public                   |
| Frontend           | React + Vite + Tailwind CSS                           |
| UI primitives      | Radix UI                                              |
| State management   | Zustand                                               |
| Relationship graph | react-force-graph                                     |
| Embeddings         | MiniLM                                                |
| LLM                | Model TBC - via OpenRouter                            |
| Package management | uv (Python), bun (JS)                                 |
| Infra              | Homelab → VPS when public, containerised from day one |

**Frontend rendering approach:** Plain React with CSS absolute positioning and `transition-all` animations. No Phaser — the town map is a static image, agent sprites are absolutely positioned PNGs that glide smoothly between locations via CSS transitions when ticks update. Phaser may be revisited later if walking-along-roads animations become a priority.

---

## Project Structure

This is all subject to change, but this gives a rough idea of how the codebase will be organised.

```
tokenbury/
├── CLAUDE.md
├── Makefile                        # make dev, make migrate etc
│
├── backend/
│   ├── pyproject.toml
│   ├── .venv/
│   ├── manage.py
│   │
│   ├── config/
│   │   ├── settings/
│   │   │   ├── base.py             # shared settings
│   │   │   ├── local.py            # SQLite, debug, CORS for Vite
│   │   │   └── production.py       # Postgres, proper secrets
│   │   ├── urls.py
│   │   ├── asgi.py                 # Django Channels entry point
│   │   └── wsgi.py
│   │
│   ├── world/                      # core models — agents, locations, ticks
│   │   ├── models.py
│   │   ├── admin.py
│   │   ├── views.py
│   │   └── migrations/
│   │
│   ├── memory/                     # memory stream, embeddings, retrieval
│   │   ├── models.py
│   │   ├── retrieval.py            # MiniLM scoring + retrieval logic
│   │   └── migrations/
│   │
│   ├── simulation/                 # tick runner, prompt building, LLM calls
│   │   ├── runner.py               # main tick loop
│   │   ├── prompts.py              # prompt template assembly
│   │   ├── llm.py                  # OpenRouter/Haiku client wrapper
│   │   ├── tasks.py                # Celery/Django Q tasks (deferred)
│   │   └── management/
│   │       └── commands/
│   │           └── run_ticker.py   # python manage.py run_ticker
│   │
│   ├── social/                     # relationships, conversations, intentions
│   │   ├── models.py
│   │   ├── resolver.py             # co-location detection, conversation generation
│   │   └── migrations/
│   │
│   ├── api/                        # DRF REST endpoints
│   │   ├── views.py
│   │   ├── serializers.py
│   │   └── urls.py
│   │
│   └── live/                       # Django Channels / WebSockets
│       ├── consumers.py
│       └── routing.py
│
└── frontend/
    ├── package.json
    ├── vite.config.js              # proxies /api/* to Django :8000
    ├── index.html
    │
    ├── public/
    │   └── assets/
    │       ├── map/                # town map image(s)
    │       ├── characters/         # agent sprite PNGs
    │       └── ui/                 # icons, misc
    │
    └── src/
        ├── main.jsx
        ├── App.jsx
        │
        ├── components/
        │   ├── town/
        │   │   ├── TownView.jsx          # map + absolutely positioned sprites
        │   │   └── LocationCard.jsx      # individual location info
        │   ├── agents/
        │   │   ├── AgentSprite.jsx       # positioned sprite with CSS transition
        │   │   ├── AgentCard.jsx         # click-to-expand character detail
        │   │   └── MemoryLog.jsx         # scrollable memory stream
        │   ├── relationships/
        │   │   └── RelationshipGraph.jsx # react-force-graph visualisation
        │   ├── timeline/
        │   │   └── TimelineScrubber.jsx  # time travel — scrub through ticks
        │   └── ui/                       # shared Radix UI based components
        │
        ├── hooks/
        │   ├── useWebSocket.js           # live tick updates → Zustand
        │   ├── useAgentHistory.js        # time travel REST queries
        │   └── useRelationships.js       # relationship state helpers
        │
        ├── api/
        │   └── client.js                 # REST API calls to Django
        │
        ├── store/
        │   └── simulation.js             # Zustand — single source of truth
        │
        └── constants/
            └── locations.js              # LOCATION_POSITIONS lookup table
```

---

## Running Locally

```bash
# both servers (recommended)
make dev

# individually
make backend    # Django on :8000
make frontend   # Vite on :5173
```

Vite proxies all `/api/*` requests to Django, so the frontend never needs to know the backend port.

---

## Django Apps

| App          | Responsibility                                                            |
| ------------ | ------------------------------------------------------------------------- |
| `world`      | Core models: `Agent`, `Tick`, `AgentTick`, `EnvironmentTreeNode`          |
| `memory`     | `Memory` model, MiniLM embeddings, retrieval scoring                      |
| `social`     | `Conversation`, `RelationshipEvent`, `Intention` — co-location resolution |
| `simulation` | Tick runner, prompt builder, LLM calls                                    |
| `api`        | DRF serialisers and REST views                                            |
| `live`       | Django Channels WebSocket consumers                                       |

---

## Core Django Models (summary)

**`Agent`** — name, bio (natural language description of personality/schedule/beliefs), active flag.

**`EnvironmentTreeNode`** — tree structure of the town. Root → locations → rooms → items. Rendered to natural language for LLM prompts ("there is a stove in the kitchen"). Has a `slug` (e.g. `harbour_cafe`) used as the canonical location identifier.

**`Tick`** — a moment in time. Has both a real-world `timestamp` and an `in_game_time`.

**`AgentTick`** — what one agent did during one tick. Location, activity, mood, inner thought, raw prompt + response (for debugging). Unique on `(agent, tick)`.

**`Memory`** — append-only. Content, importance score (1–10, self-rated by agent), MiniLM embedding, tick reference.

**`Conversation`** — summary of a conversation between agents who were co-located during a tick.

**`RelationshipEvent`** — append-only delta event on three axes: familiarity, warmth, trust. Sum all events up to a given tick to get relationship state at that moment.

**`Intention`** — an agent proposing a future meetup to another agent. Status: pending → accepted/declined → completed/expired.

---

## Agent Tick Prompt Structure

Each tick, every agent gets an isolated prompt built from 8 sections:

1. **Global static** — what Tokenbury is, rules of the simulation
2. **Global dynamic** — current time, weather, season, active world themes
3. **Character static** — bio, traits, beliefs, interests
4. **Character dynamic** — current mood, energy, carry-over from last tick
5. **Character relationships** — condensed warmth/trust summary for known agents
6. **Character relevant memories** — top N retrieved via MiniLM scoring
7. **World state snapshot** — where other agents are and what they're doing
8. **Pending intentions** — invitations received, planned meetups

Static sections are cached. Only dynamic sections recompute each tick.

---

## Expected LLM Output Per Tick

```json
{
  "activity": "Having coffee at the harbour café",
  "location": "harbour_cafe",
  "mood": "content",
  "inner_thought": "I wonder if Sarah is still upset with me",
  "intention": {
    "target_agent": "sarah",
    "proposed_time": "19:00",
    "activity": "meet for a walk"
  }
}
```

---

## Memory Retrieval Scoring

```python
score = (
    recency_weight * recency_score(memory)
    + importance_weight * memory.importance
    + relevance_weight * cosine_similarity(memory, current_context)
)
```

Importance is self-rated by the agent at write time (1–10). Relevance uses MiniLM cosine similarity. Top N memories are retrieved per tick within a ~300 token budget.

---

## WebSocket Tick Payload

When a tick completes, Django Channels broadcasts this shape to all connected clients:

```json
{
  "tick_id": 42,
  "in_game_time": "2024-03-15T14:00:00",
  "agents": [
    {
      "id": 1,
      "name": "Margaret",
      "location": "harbour_cafe",
      "activity": "Reading the newspaper",
      "mood": "content",
      "inner_thought": "I wonder if the fishing boats are back yet"
    }
  ]
}
```

The Zustand store is the single source of truth on the frontend. The `useWebSocket` hook writes incoming tick payloads to the store, and all React components subscribe to it.

---

## Frontend Location System

Agent positions on the map are driven by a static lookup table:

```javascript
// src/constants/locations.js
export const LOCATION_POSITIONS = {
  harbour_cafe: { x: 340, y: 210 },
  pub: { x: 520, y: 180 },
  beach: { x: 200, y: 480 },
  // ...
};
```

When an agent's location changes, the sprite transitions smoothly via CSS (`transition-all duration-[2000ms]`). No pathfinding — sprites glide in a straight line, which looks fine at town-map scale.

---

## What's Deliberately Deferred

These are planned but not part of the initial build:

- Memory retrieval (first ticks use bio only, no retrieved memories)
- Co-location conversation generation
- Celery / Django Q task queue (management command first)
- Relationship scoring
- Intention system
- Agent reflection (higher-level memory synthesis)
- Agent perception subgraphs (agents knowing only what they've seen)
- Postgres migration
- Any form of user interaction beyond read-only viewing


# Git Workflow
- `main` branch is always deployable, contains production-ready code.
- Use conventional commits for clear history and changelog generation. Scope should not be included.
- Use pre-commit hooks for testing, linting and formatting (e.g. `ruff`, `eslint`, `prettier`).
- Tests should always pass before commiting. There is no such thing as "pre-existing issue" - if you find an issue with the tests, fix it and commit.
