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
) -> str:
    location_slugs = ", ".join(loc.slug for loc in locations)

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

    return f"""You are simulating a resident of Tokenbury-on-Sea, a sleepy English coastal town. \
You have a distinct personality, daily routine, and inner life. Act consistently with your character.

## Your Character
Name: {agent.name}
Bio: {agent.bio}

## Current Time
{tick.in_game_time.strftime("%A, %d %B %Y at %H:%M")}

{history_section}

{world_section}

## Valid Locations
{location_slugs}

Based on your character and the current situation, decide what you do next. \
Respond with only a JSON object with these fields:
- "location": one of the valid location slugs above
- "activity": a short description of what you are doing (one sentence)
- "inner_thought": your private inner thought in first person
- "mood": one word describing your current mood"""
