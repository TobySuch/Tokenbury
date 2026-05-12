from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field

from django.conf import settings

from world.models import Agent, AgentTick, DailyPlan, Location, Tick

from .llm import call_llm
from .prompts import build_activity_prompt, build_location_prompt

logger = logging.getLogger(__name__)


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


@dataclass
class TickContext:
    tick: Tick
    agents: list[Agent]
    locations: list[Location]
    location_by_slug: dict[str, Location]
    world_state: list[dict]

    # Populated by LocationResolutionStep, keyed by agent.id
    resolved_locations: dict[int, Location | None] = field(default_factory=dict)
    intentions: dict[int, str] = field(default_factory=dict)
    phase1_prompts: dict[int, str] = field(default_factory=dict)
    phase1_responses: dict[int, str] = field(default_factory=dict)

    @property
    def co_located_agents(self) -> dict[str, list[Agent]]:
        """Groups agents by their resolved location slug. Agents with no resolved location are excluded."""
        groups: dict[str, list[Agent]] = defaultdict(list)
        for agent in self.agents:
            loc = self.resolved_locations.get(agent.id)
            if loc is not None:
                groups[loc.slug].append(agent)
        return dict(groups)


class PerAgentStep(ABC):
    """A pipeline step that runs once per agent per tick."""

    @abstractmethod
    def run(self, agent: Agent, ctx: TickContext) -> None:
        """Process a single agent. Raise to trigger the per-agent error handler."""
        ...


class LocationResolutionStep(PerAgentStep):
    """Phase 1: Decide where each agent will be this tick and optionally generate a daily plan."""

    def run(self, agent: Agent, ctx: TickContext) -> None:
        day_start = ctx.tick.in_game_time.replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        previous_agent_ticks = list(
            AgentTick.objects
            .filter(
                agent=agent,
                tick__in_game_time__gte=day_start,
                tick__in_game_time__lt=ctx.tick.in_game_time,
            )
            .select_related("tick", "location")
            .order_by("tick__in_game_time")
        )

        today = ctx.tick.in_game_time.date()
        existing_plan = DailyPlan.objects.filter(agent=agent, date=today).first()
        needs_plan = (
            existing_plan is None and ctx.tick.in_game_time.hour >= settings.PLAN_HOUR
        )
        daily_plan = existing_plan.plan if existing_plan else None

        prompt = build_location_prompt(
            agent,
            ctx.tick,
            previous_agent_ticks,
            ctx.world_state,
            ctx.locations,
            daily_plan=daily_plan,
            needs_plan=needs_plan,
        )

        logger.info(
            "LLM call — tick %d (%s) | agent %s | phase LocationResolution",
            ctx.tick.id,
            ctx.tick.in_game_time.strftime("%H:%M"),
            agent.name,
        )
        raw_response = call_llm(prompt)
        ctx.phase1_prompts[agent.id] = prompt
        ctx.phase1_responses[agent.id] = raw_response

        try:
            data = json.loads(_extract_json(raw_response))
        except json.JSONDecodeError as exc:
            logger.error(
                "Agent %s (phase 1) returned invalid JSON: %s — raw: %.200s",
                agent.name,
                exc,
                raw_response,
            )
            raise

        if needs_plan:
            plan_items = data.get("daily_plan")
            if isinstance(plan_items, list) and plan_items:
                DailyPlan.objects.create(
                    agent=agent,
                    date=today,
                    plan=[str(item) for item in plan_items],
                    generated_at_tick=ctx.tick,
                )
                logger.info("Created daily plan for %s on %s", agent.name, today)
            else:
                logger.warning(
                    "Agent %s did not return a valid daily_plan — got %r",
                    agent.name,
                    plan_items,
                )

        slug = data.get("location", "").strip().lower()
        location = ctx.location_by_slug.get(slug)
        if slug and not location:
            logger.warning(
                "Agent %s returned unknown location slug %r", agent.name, slug
            )

        ctx.resolved_locations[agent.id] = location
        ctx.intentions[agent.id] = data.get("intention", "")


class ActivityGenerationStep(PerAgentStep):
    """Phase 2: Generate activity, mood, and inner thought now that all locations are known."""

    def run(self, agent: Agent, ctx: TickContext) -> None:
        if agent.id not in ctx.resolved_locations:
            logger.warning(
                "Skipping activity generation for %s — phase 1 did not complete",
                agent.name,
            )
            return

        resolved_location = ctx.resolved_locations[agent.id]
        intention = ctx.intentions.get(agent.id, "")

        co_located_slug = resolved_location.slug if resolved_location else ""
        co_located = [
            (a.name, a.bio)
            for a in ctx.co_located_agents.get(co_located_slug, [])
            if a.id != agent.id
        ]

        day_start = ctx.tick.in_game_time.replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        previous_agent_ticks = list(
            AgentTick.objects
            .filter(
                agent=agent,
                tick__in_game_time__gte=day_start,
                tick__in_game_time__lt=ctx.tick.in_game_time,
            )
            .select_related("tick", "location")
            .order_by("tick__in_game_time")
        )

        prompt = build_activity_prompt(
            agent,
            ctx.tick,
            previous_agent_ticks,
            resolved_location,
            intention,
            co_located,
        )

        logger.info(
            "LLM call — tick %d (%s) | agent %s | phase ActivityGeneration",
            ctx.tick.id,
            ctx.tick.in_game_time.strftime("%H:%M"),
            agent.name,
        )
        raw_response = call_llm(prompt)

        try:
            data = json.loads(_extract_json(raw_response))
        except json.JSONDecodeError as exc:
            logger.error(
                "Agent %s (phase 2) returned invalid JSON: %s — raw: %.200s",
                agent.name,
                exc,
                raw_response,
            )
            raise

        normalised = _normalise(data)

        AgentTick.objects.create(
            agent=agent,
            tick=ctx.tick,
            location=resolved_location,
            activity=normalised["activity"],
            inner_thought=normalised["inner_thought"],
            mood=normalised["mood"],
            raw_prompts={
                "LocationResolutionStep": ctx.phase1_prompts.get(agent.id, ""),
                "ActivityGenerationStep": prompt,
            },
            raw_responses={
                "LocationResolutionStep": ctx.phase1_responses.get(agent.id, ""),
                "ActivityGenerationStep": raw_response,
            },
        )
