import logging
import math
from datetime import datetime, timedelta

from django.conf import settings
from django.utils import timezone as tz

from world.models import Agent, AgentTick, Instance, Location, Tick

from .pipeline import (
    ActivityGenerationStep,
    LocationResolutionStep,
    PerAgentStep,
    TickContext,
)

logger = logging.getLogger(__name__)


class SimulationAlreadyUpToDate(Exception):
    def __init__(self, tick: Tick) -> None:
        self.tick = tick
        super().__init__(f"Already up to date at {tick.in_game_time.isoformat()}")


def _round_to_interval(dt: datetime, interval_minutes: int) -> datetime:
    total_seconds = interval_minutes * 60
    epoch = dt.replace(hour=0, minute=0, second=0, microsecond=0)
    delta = (dt - epoch).total_seconds()
    rounded = round(delta / total_seconds) * total_seconds
    return epoch + timedelta(seconds=rounded)


def _ceil_to_interval(dt: datetime, interval_minutes: int) -> datetime:
    total_seconds = interval_minutes * 60
    epoch = dt.replace(hour=0, minute=0, second=0, microsecond=0)
    delta = (dt - epoch).total_seconds()
    ceiled = math.ceil(delta / total_seconds) * total_seconds
    return epoch + timedelta(seconds=ceiled)


def run_tick(catchup: bool = False) -> Tick:
    interval = settings.TICK_INTERVAL_MINUTES
    instance = Instance.objects.filter(active=True).first()

    # Intentionally no active filter — even a partially-processed tick represents
    # a point in time and partial world state that is useful context for the next run.
    previous_tick = (
        Tick.objects.filter(instance=instance).order_by("-in_game_time").first()
    )

    if previous_tick is None:
        in_game_time = _round_to_interval(tz.now(), interval)
    elif catchup:
        ceiled = _ceil_to_interval(tz.now(), interval)
        if ceiled > previous_tick.in_game_time:
            in_game_time = ceiled
        else:
            raise SimulationAlreadyUpToDate(previous_tick)
    else:
        in_game_time = previous_tick.in_game_time + timedelta(minutes=interval)

    tick = Tick.objects.create(in_game_time=in_game_time, instance=instance)
    logger.info("Created tick %d at %s", tick.id, in_game_time)

    agents = list(Agent.objects.filter(active=True, instance=instance))
    locations = list(Location.objects.filter(instance=instance))

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
