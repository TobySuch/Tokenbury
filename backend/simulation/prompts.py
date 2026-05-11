from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from world.models import Agent, AgentTick, Location, Tick


def build_agent_prompt(
    agent: "Agent",
    tick: "Tick",
    previous_agent_ticks: list["AgentTick"],
    world_state: list[dict],
    locations: list["Location"],
    daily_plan: list[str] | None = None,
    needs_plan: bool = False,
) -> str:
    location_slugs = ", ".join(loc.slug for loc in locations)

    if daily_plan is not None:
        plan_lines = "\n".join(f"  - {item}" for item in daily_plan)
        plan_section = f"## Your Plan for Today\n{plan_lines}\n\n"
    else:
        plan_section = ""

    if previous_agent_ticks:
        history_lines = []
        for at in previous_agent_ticks:
            loc_name = at.location.slug if at.location else "unknown"
            history_lines.append(
                f"  {at.tick.in_game_time.strftime('%H:%M')} — at {loc_name}, {at.activity} (mood: {at.mood})"
            )
        history_section = "## Your Day So Far\n" + "\n".join(history_lines)
    else:
        history_section = "## Your Day So Far\nThis is the start of your day."

    if world_state:
        world_lines = []
        for entry in world_state:
            world_lines.append(
                f"  {entry['name']} is at {entry['location']} — {entry['activity']}"
            )
        world_section = "## Current World State\n" + "\n".join(world_lines)
    else:
        world_section = "## Current World State\nYou are the only one around."

    if needs_plan:
        plan_field = (
            '\n- "daily_plan": a list of 3 to 6 intentions for the rest of today, each with a '
            "rough time prefix in HH:MM format "
            '(e.g. "08:00 — Have breakfast at the harbour café", "14:00 — Call in on Bernard")'
        )
    else:
        plan_field = ""

    return f"""You are simulating a resident of Tokenbury-on-Sea, a sleepy English coastal town. \
You have a distinct personality, daily routine, and inner life. Act consistently with your character.

## Your Character
Name: {agent.name}
Bio: {agent.bio}

## Current Time
{tick.in_game_time.strftime("%A, %d %B %Y at %H:%M")}

{plan_section}{history_section}

{world_section}

## Valid Locations
{location_slugs}

Based on your character and the current situation, decide what you do next. \
Respond with only a JSON object with these fields:
- "location": one of the valid location slugs above
- "activity": a short description of what you are doing (one sentence)
- "inner_thought": your private inner thought in first person
- "mood": one word describing your current mood{plan_field}"""
