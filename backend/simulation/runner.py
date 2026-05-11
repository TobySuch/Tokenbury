import logging
from datetime import timedelta

from django.conf import settings
from django.utils import timezone as tz

from world.models import Agent, AgentTick, Location, Tick

from .pipeline import (
    ActivityGenerationStep,
    LocationResolutionStep,
    PerAgentStep,
    TickContext,
)

logger = logging.getLogger(__name__)


def run_tick() -> Tick:
    # Intentionally no active filter — even a partially-processed tick represents
    # a point in time and partial world state that is useful context for the next run.
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

    ctx = TickContext(
        tick=tick,
        agents=agents,
        locations=locations,
        location_by_slug={loc.slug: loc for loc in locations},
        world_state=_build_world_state(previous_tick),
    )

    steps: list[PerAgentStep] = [
        LocationResolutionStep(),
        ActivityGenerationStep(),
    ]

    for step in steps:
        processed = 0
        for agent in agents:
            try:
                step.run(agent, ctx)
                processed += 1
            except Exception:
                logger.exception(
                    "[%s] Failed for agent %s (id=%d)",
                    type(step).__name__,
                    agent.name,
                    agent.id,
                )
        logger.info(
            "[%s] %d/%d agents processed",
            type(step).__name__,
            processed,
            len(agents),
        )

    tick.active = True
    tick.save(update_fields=["active"])

    logger.info("Tick %d complete", tick.id)
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
