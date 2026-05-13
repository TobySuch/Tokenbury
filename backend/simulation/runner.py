import json
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
    _extract_json,
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


def _resume_tick(tick: Tick, instance: Instance) -> None:
    agents = list(Agent.objects.filter(active=True, instance=instance))
    locations = list(Location.objects.filter(instance=instance))

    completed_ids = set(
        AgentTick.objects.filter(tick=tick).values_list("agent_id", flat=True)
    )
    missing_agents = [a for a in agents if a.id not in completed_ids]

    logger.info(
        "Resuming tick %d: %d/%d complete, re-running %d agent(s)",
        tick.id,
        len(completed_ids),
        len(agents),
        len(missing_agents),
    )

    if not missing_agents:
        tick.active = True
        tick.save(update_fields=["active"])
        return

    previous_complete = (
        Tick.objects
        .filter(
            instance=instance,
            active=True,
            in_game_time__lt=tick.in_game_time,
        )
        .order_by("-in_game_time")
        .first()
    )

    ctx = TickContext(
        tick=tick,
        agents=agents,
        locations=locations,
        location_by_slug={loc.slug: loc for loc in locations},
        world_state=_build_world_state(previous_complete),
    )

    for at in AgentTick.objects.filter(tick=tick).select_related("agent", "location"):
        ctx.resolved_locations[at.agent_id] = at.location
        ctx.phase1_prompts[at.agent_id] = at.raw_prompts.get(
            "LocationResolutionStep", ""
        )
        ctx.phase1_responses[at.agent_id] = at.raw_responses.get(
            "LocationResolutionStep", ""
        )
        try:
            data = json.loads(
                _extract_json(at.raw_responses.get("LocationResolutionStep", ""))
            )
            ctx.intentions[at.agent_id] = data.get("intention", "")
        except json.JSONDecodeError, ValueError:
            ctx.intentions[at.agent_id] = ""

    phase1 = LocationResolutionStep()
    for agent in missing_agents:
        try:
            phase1.run(agent, ctx)
        except Exception:
            logger.exception(
                "[Resume/LocationResolutionStep] Failed for agent %s (id=%d)",
                agent.name,
                agent.id,
            )

    phase2 = ActivityGenerationStep()
    for agent in missing_agents:
        try:
            phase2.run(agent, ctx)
        except Exception:
            logger.exception(
                "[Resume/ActivityGenerationStep] Failed for agent %s (id=%d)",
                agent.name,
                agent.id,
            )

    tick.active = True
    tick.save(update_fields=["active"])
    logger.info("Tick %d resumed and completed", tick.id)


def _recover_abandoned_ticks(instance: Instance) -> None:
    abandoned = list(
        Tick.objects.filter(instance=instance, active=False).order_by("in_game_time")
    )
    if abandoned:
        logger.warning("Found %d abandoned tick(s); resuming", len(abandoned))
    for tick in abandoned:
        _resume_tick(tick, instance)


def run_tick(catchup: bool = False) -> Tick:
    interval = settings.TICK_INTERVAL_MINUTES
    instance = Instance.objects.filter(active=True).first()

    _recover_abandoned_ticks(instance)

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
