from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from world.models import Agent, AgentTick, Location, Tick


def build_location_prompt(
    agent: "Agent",
    tick: "Tick",
    previous_agent_ticks: list["AgentTick"],
    world_state: list[dict],
    locations: list["Location"],
    daily_plan: list[str] | None = None,
    needs_plan: bool = False,
) -> str:
    location_slugs = ", ".join(loc.slug for loc in locations)
    location_lines = "\n".join(
        f"  - {loc.slug} ({loc.name}): {loc.description}" for loc in locations
    )

    if daily_plan is not None:
        plan_lines = "\n".join(f"  - {item}" for item in daily_plan)
        plan_section = f"## Your Plan for Today\n{plan_lines}\n\n"
    else:
        plan_section = ""

    if previous_agent_ticks:
        history_lines = [
            f"  {at.tick.in_game_time.strftime('%H:%M')} — at {at.location.slug if at.location else 'unknown'}, {at.activity} (mood: {at.mood})"
            for at in previous_agent_ticks
        ]
        history_section = "## Your Day So Far\n" + "\n".join(history_lines)
    else:
        history_section = "## Your Day So Far\nThis is the start of your day."

    if world_state:
        world_lines = [
            f"  {entry['name']} is at {entry['location']} — {entry['activity']}"
            for entry in world_state
        ]
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
{location_lines}

Based on your character and the current situation, decide where you will be during this time period. \
Respond with only a JSON object with these fields:
- "location": one of the valid location slugs above (e.g. {location_slugs})
- "intention": one sentence describing what you intend to do at that location{plan_field}"""


def build_activity_prompt(
    agent: "Agent",
    tick: "Tick",
    previous_agent_ticks: list["AgentTick"],
    resolved_location: "Location | None",
    intention: str,
    co_located: list[tuple[str, str]],
) -> str:
    if previous_agent_ticks:
        history_lines = [
            f"  {at.tick.in_game_time.strftime('%H:%M')} — at {at.location.slug if at.location else 'unknown'}, {at.activity} (mood: {at.mood})"
            for at in previous_agent_ticks
        ]
        history_section = "## Your Day So Far\n" + "\n".join(history_lines)
    else:
        history_section = "## Your Day So Far\nThis is the start of your day."

    if resolved_location:
        location_detail = f"{resolved_location.name}: {resolved_location.description}"
        if intention:
            location_detail += f"\nYour intention here: {intention}"
        location_section = f"## Your Current Location\n{location_detail}"
    else:
        location_section = "## Your Current Location\nSomewhere in town."

    if co_located:
        co_lines = "\n".join(f"  - {name}: {bio}" for name, bio in co_located)
        colocated_section = f"## Others Here With You\n{co_lines}"
    else:
        colocated_section = "## Others Here With You\nYou are alone here."

    return f"""You are simulating a resident of Tokenbury-on-Sea, a sleepy English coastal town. \
You have a distinct personality, daily routine, and inner life. Act consistently with your character.

## Your Character
Name: {agent.name}
Bio: {agent.bio}

## Current Time
{tick.in_game_time.strftime("%A, %d %B %Y at %H:%M")}

{history_section}

{location_section}

{colocated_section}

Based on where you are and who is around you, decide what you are doing and how you feel. \
Respond with only a JSON object with these fields:
- "activity": a short description of what you are doing (one sentence)
- "inner_thought": your private inner thought in first person
- "mood": one word describing your current mood"""
