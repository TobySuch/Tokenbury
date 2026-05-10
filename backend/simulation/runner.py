import json
import logging
from datetime import timedelta

from django.conf import settings
from django.utils import timezone as tz

from world.models import Agent, AgentTick, Location, Tick

from .llm import call_llm
from .prompts import build_agent_prompt

logger = logging.getLogger(__name__)


def run_tick() -> Tick:
    previous_tick = Tick.objects.order_by("-in_game_time").first()

    if previous_tick is None:
        in_game_time = tz.now()
    else:
        in_game_time = previous_tick.in_game_time + timedelta(
            minutes=settings.TICK_INTERVAL_MINUTES
        )

    tick = Tick.objects.create(in_game_time=in_game_time)
    logger.info("Created tick %d at %s", tick.id, in_game_time)

    agents = list(Agent.objects.filter(active=True))
    locations = list(Location.objects.all())
    location_by_slug = {loc.slug: loc for loc in locations}

    world_state = _build_world_state(previous_tick)

    processed = 0
    for agent in agents:
        try:
            _process_agent(agent, tick, world_state, locations, location_by_slug)
            processed += 1
        except Exception:
            logger.exception("Failed to process agent %s (id=%d)", agent.name, agent.id)

    logger.info(
        "Tick %d complete — %d/%d agents processed", tick.id, processed, len(agents)
    )
    return tick


def _build_world_state(previous_tick: Tick | None) -> list[dict]:
    if previous_tick is None:
        return []

    agent_ticks = AgentTick.objects.filter(tick=previous_tick).select_related(
        "agent", "location"
    )
    return [
        {
            "name": at.agent.name,
            "location": at.location.slug if at.location else "unknown",
            "activity": at.activity,
        }
        for at in agent_ticks
    ]


def _normalise(data: dict) -> dict:
    """Normalise LLM output fields before persisting."""
    activity = data.get("activity", "").strip()
    inner_thought = data.get("inner_thought", "").strip()
    mood = data.get("mood", "").strip().lower()
    return {
        # [:1].upper() rather than capitalize() to avoid lowercasing the rest (e.g. "BBC", "I")
        "activity": activity[:1].upper() + activity[1:] if activity else "",
        "inner_thought": inner_thought[:1].upper() + inner_thought[1:]
        if inner_thought
        else "",
        "mood": mood,
    }


def _extract_json(text: str) -> str:
    """Strip markdown fences or other wrapping and return the bare JSON object."""
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        return text
    return text[start : end + 1]


def _process_agent(
    agent: Agent,
    tick: Tick,
    world_state: list[dict],
    locations: list[Location],
    location_by_slug: dict[str, Location],
) -> None:
    day_start = tick.in_game_time.replace(hour=0, minute=0, second=0, microsecond=0)
    previous_agent_ticks = list(
        AgentTick.objects
        .filter(
            agent=agent,
            tick__in_game_time__gte=day_start,
            tick__in_game_time__lt=tick.in_game_time,
        )
        .select_related("tick", "location")
        .order_by("tick__in_game_time")
    )

    prompt = build_agent_prompt(
        agent, tick, previous_agent_ticks, world_state, locations
    )

    raw_response = call_llm(prompt)

    try:
        data = json.loads(_extract_json(raw_response))
    except json.JSONDecodeError as exc:
        logger.error(
            "Agent %s returned invalid JSON: %s — raw: %.200s",
            agent.name,
            exc,
            raw_response,
        )
        raise

    slug = data.get("location", "").strip().lower()
    location = location_by_slug.get(slug)
    if slug and not location:
        logger.warning("Agent %s returned unknown location slug %r", agent.name, slug)

    normalised = _normalise(data)

    AgentTick.objects.create(
        agent=agent,
        tick=tick,
        location=location,
        activity=normalised["activity"],
        inner_thought=normalised["inner_thought"],
        mood=normalised["mood"],
        raw_prompt=prompt,
        raw_response=raw_response,
    )
