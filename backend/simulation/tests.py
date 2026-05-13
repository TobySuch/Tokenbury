import json
from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest
from django.utils import timezone as tz

from world.models import Agent, AgentTick, DailyPlan, Instance, Location, Tick

from simulation.llm import LLMError, call_llm
from simulation.pipeline import TickContext, _extract_json, _normalise
from simulation.prompts import build_activity_prompt, build_location_prompt
from simulation.runner import (
    SimulationAlreadyUpToDate,
    _ceil_to_interval,
    _round_to_interval,
    run_tick,
)


# --- factories ---


def make_instance():
    inst, _ = Instance.objects.get_or_create(
        slug="test-instance",
        defaults={
            "name": "Test Instance",
            "map_image": "maps/test.png",
            "active": True,
        },
    )
    return inst


def make_agent(name="Margaret", active=True, instance=None):
    if instance is None:
        instance = make_instance()
    return Agent.objects.create(
        instance=instance,
        name=name,
        bio=f"{name} is a retired teacher who loves the sea.",
        sprite="sprites/margaret.png",
        active=active,
    )


def make_location(slug="harbour_cafe", name="Harbour Café", instance=None):
    if instance is None:
        instance = make_instance()
    return Location.objects.create(
        instance=instance,
        slug=slug,
        name=name,
        description="A cosy café overlooking the harbour.",
        bbox_x1=0.0,
        bbox_y1=0.0,
        bbox_x2=100.0,
        bbox_y2=100.0,
    )


def make_tick(in_game_time=None, active=True, instance=None):
    if in_game_time is None:
        in_game_time = tz.now()
    if instance is None:
        instance = make_instance()
    return Tick.objects.create(
        in_game_time=in_game_time, active=active, instance=instance
    )


def make_agent_tick(
    agent, tick, location=None, activity="Drinking coffee", mood="content"
):
    return AgentTick.objects.create(
        agent=agent,
        tick=tick,
        location=location,
        activity=activity,
        inner_thought="Just enjoying the morning.",
        mood=mood,
    )


# Two-phase response fixtures.
# Using a combined response so both phases can parse from the same mock value —
# each phase just picks the fields it needs and ignores the rest.
VALID_LLM_RESPONSE = json.dumps({
    "location": "harbour_cafe",
    "intention": "Having a quiet coffee and reading the morning paper",
    "activity": "Reading the newspaper",
    "inner_thought": "I wonder if the boats are back.",
    "mood": "peaceful",
})

VALID_LLM_RESPONSE_WITH_PLAN = json.dumps({
    "location": "harbour_cafe",
    "intention": "Having a quiet coffee and reading the morning paper",
    "activity": "Reading the newspaper",
    "inner_thought": "I wonder if the boats are back.",
    "mood": "peaceful",
    "daily_plan": [
        "08:00 — Have breakfast at the harbour café",
        "11:00 — Visit Margaret at her cottage",
        "13:00 — Pick up a newspaper from the corner shop",
    ],
})

FENCED_LLM_RESPONSE = f"```json\n{VALID_LLM_RESPONSE}\n```"


def two_phase_responses(n_agents=1, phase1=None, phase2=None):
    """Build a side_effect list for n agents × 2 phases."""
    p1 = phase1 or VALID_LLM_RESPONSE
    p2 = phase2 or VALID_LLM_RESPONSE
    return [p1] * n_agents + [p2] * n_agents


# --- _normalise tests ---


def test_normalise_capitalises_activity():
    result = _normalise({
        "activity": "reading the newspaper",
        "inner_thought": "",
        "mood": "",
    })
    assert result["activity"] == "Reading the newspaper"


def test_normalise_capitalises_inner_thought():
    result = _normalise({
        "activity": "",
        "inner_thought": "i wonder about the sea",
        "mood": "",
    })
    assert result["inner_thought"] == "I wonder about the sea"


def test_normalise_lowercases_mood():
    result = _normalise({"activity": "", "inner_thought": "", "mood": "Content"})
    assert result["mood"] == "content"


def test_normalise_strips_whitespace():
    result = _normalise({
        "activity": "  Fishing  ",
        "inner_thought": "  Quiet day.  ",
        "mood": "  Calm  ",
    })
    assert result["activity"] == "Fishing"
    assert result["inner_thought"] == "Quiet day."
    assert result["mood"] == "calm"


def test_normalise_handles_empty_fields():
    result = _normalise({})
    assert result == {"activity": "", "inner_thought": "", "mood": ""}


# --- _extract_json tests ---


def test_extract_json_bare():
    assert _extract_json('{"a": 1}') == '{"a": 1}'


def test_extract_json_strips_markdown_fence():
    fenced = '```json\n{"a": 1}\n```'
    assert _extract_json(fenced) == '{"a": 1}'


def test_extract_json_strips_fence_without_language():
    fenced = '```\n{"a": 1}\n```'
    assert _extract_json(fenced) == '{"a": 1}'


def test_extract_json_returns_original_when_no_braces():
    assert _extract_json("not json at all") == "not json at all"


# --- TickContext tests ---


@pytest.mark.django_db
def test_tick_context_co_located_groups_by_resolved_location():
    loc_a = make_location(slug="harbour_cafe", name="Harbour Café")
    loc_b = make_location(slug="pub", name="The Pub")
    tick = make_tick()
    agent1 = make_agent("Margaret")
    agent2 = make_agent("Bernard")
    agent3 = make_agent("Evelyn")

    ctx = TickContext(
        tick=tick,
        agents=[agent1, agent2, agent3],
        locations=[loc_a, loc_b],
        location_by_slug={"harbour_cafe": loc_a, "pub": loc_b},
        world_state=[],
        resolved_locations={
            agent1.id: loc_a,
            agent2.id: loc_a,
            agent3.id: loc_b,
        },
    )

    groups = ctx.co_located_agents
    assert len(groups["harbour_cafe"]) == 2
    assert len(groups["pub"]) == 1


@pytest.mark.django_db
def test_tick_context_co_located_excludes_unresolved():
    loc = make_location()
    tick = make_tick()
    agent1 = make_agent("Margaret")
    agent2 = make_agent("Bernard")

    ctx = TickContext(
        tick=tick,
        agents=[agent1, agent2],
        locations=[loc],
        location_by_slug={"harbour_cafe": loc},
        world_state=[],
        resolved_locations={agent1.id: loc},  # agent2 has no resolved location
    )

    groups = ctx.co_located_agents
    assert agent1 in groups["harbour_cafe"]
    assert agent2 not in groups.get("harbour_cafe", [])


# --- location prompt tests ---


@pytest.mark.django_db
def test_location_prompt_contains_agent_bio():
    agent = make_agent()
    tick = make_tick()
    location = make_location()
    prompt = build_location_prompt(agent, tick, [], [], [location])
    assert agent.bio in prompt


@pytest.mark.django_db
def test_location_prompt_contains_previous_ticks():
    agent = make_agent()
    location = make_location()
    earlier_tick = make_tick(tz.now() - timedelta(hours=1))
    at = make_agent_tick(
        agent, earlier_tick, location=location, activity="Buying bread"
    )
    current_tick = make_tick()
    prompt = build_location_prompt(agent, current_tick, [at], [], [location])
    assert "Buying bread" in prompt


@pytest.mark.django_db
def test_location_prompt_empty_history_when_no_prior_ticks():
    agent = make_agent()
    tick = make_tick()
    location = make_location()
    prompt = build_location_prompt(agent, tick, [], [], [location])
    assert "start of your day" in prompt


@pytest.mark.django_db
def test_location_prompt_contains_valid_locations():
    agent = make_agent()
    tick = make_tick()
    loc1 = make_location(slug="harbour_cafe", name="Harbour Café")
    loc2 = make_location(slug="pub", name="The Pub")
    prompt = build_location_prompt(agent, tick, [], [], [loc1, loc2])
    assert "harbour_cafe" in prompt
    assert "pub" in prompt


@pytest.mark.django_db
def test_location_prompt_contains_location_descriptions():
    agent = make_agent()
    tick = make_tick()
    location = make_location(slug="harbour_cafe", name="Harbour Café")
    prompt = build_location_prompt(agent, tick, [], [], [location])
    assert "A cosy café overlooking the harbour." in prompt


@pytest.mark.django_db
def test_location_prompt_contains_world_state():
    agent = make_agent()
    tick = make_tick()
    location = make_location()
    world_state = [
        {"name": "Bernard", "location": "harbour_cafe", "activity": "Fishing"}
    ]
    prompt = build_location_prompt(agent, tick, [], world_state, [location])
    assert "Bernard" in prompt
    assert "Fishing" in prompt


@pytest.mark.django_db
def test_location_prompt_asks_for_location_and_intention():
    agent = make_agent()
    tick = make_tick()
    location = make_location()
    prompt = build_location_prompt(agent, tick, [], [], [location])
    assert '"location"' in prompt
    assert '"intention"' in prompt


@pytest.mark.django_db
def test_location_prompt_includes_existing_plan():
    agent = make_agent()
    tick = make_tick()
    location = make_location()
    plan = ["Buy fish from the harbour", "Visit Margaret"]
    prompt = build_location_prompt(agent, tick, [], [], [location], daily_plan=plan)
    assert "Buy fish from the harbour" in prompt
    assert "Visit Margaret" in prompt
    assert "Your Plan for Today" in prompt


@pytest.mark.django_db
def test_location_prompt_needs_plan_adds_daily_plan_field():
    agent = make_agent()
    tick = make_tick()
    location = make_location()
    prompt = build_location_prompt(agent, tick, [], [], [location], needs_plan=True)
    assert "daily_plan" in prompt


@pytest.mark.django_db
def test_location_prompt_no_plan_section_when_plan_is_none():
    agent = make_agent()
    tick = make_tick()
    location = make_location()
    prompt = build_location_prompt(agent, tick, [], [], [location])
    assert "Your Plan for Today" not in prompt


# --- activity prompt tests ---


@pytest.mark.django_db
def test_activity_prompt_contains_agent_bio():
    agent = make_agent()
    tick = make_tick()
    location = make_location()
    prompt = build_activity_prompt(agent, tick, [], location, "Having coffee", [])
    assert agent.bio in prompt


@pytest.mark.django_db
def test_activity_prompt_contains_resolved_location():
    agent = make_agent()
    tick = make_tick()
    location = make_location(slug="harbour_cafe", name="Harbour Café")
    prompt = build_activity_prompt(agent, tick, [], location, "", [])
    assert "Harbour Café" in prompt
    assert "A cosy café overlooking the harbour." in prompt


@pytest.mark.django_db
def test_activity_prompt_contains_intention():
    agent = make_agent()
    tick = make_tick()
    location = make_location()
    prompt = build_activity_prompt(
        agent, tick, [], location, "Catching up on the news", []
    )
    assert "Catching up on the news" in prompt


@pytest.mark.django_db
def test_activity_prompt_contains_co_located_agents():
    agent = make_agent("Margaret")
    tick = make_tick()
    location = make_location()
    co_located = [("Bernard", "A gruff retired fisherman.")]
    prompt = build_activity_prompt(agent, tick, [], location, "", co_located)
    assert "Bernard" in prompt
    assert "A gruff retired fisherman." in prompt


@pytest.mark.django_db
def test_activity_prompt_alone_when_no_co_located():
    agent = make_agent()
    tick = make_tick()
    location = make_location()
    prompt = build_activity_prompt(agent, tick, [], location, "", [])
    assert "alone" in prompt.lower()


@pytest.mark.django_db
def test_activity_prompt_asks_for_activity_mood_thought():
    agent = make_agent()
    tick = make_tick()
    location = make_location()
    prompt = build_activity_prompt(agent, tick, [], location, "", [])
    assert '"activity"' in prompt
    assert '"inner_thought"' in prompt
    assert '"mood"' in prompt


@pytest.mark.django_db
def test_activity_prompt_does_not_contain_valid_locations_list():
    agent = make_agent()
    tick = make_tick()
    location = make_location()
    prompt = build_activity_prompt(agent, tick, [], location, "", [])
    assert "Valid Locations" not in prompt


# --- LLM client tests ---


def _make_urlopen_mock(response_body: dict, status: int = 200):
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(response_body).encode()
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    return mock_resp


@patch("simulation.llm.settings")
@patch("simulation.llm.urllib.request.urlopen")
def test_call_llm_sends_correct_payload(mock_urlopen, mock_settings):
    mock_settings.OPENROUTER_API_KEY = "test-key"
    mock_settings.LLM_MODEL = "anthropic/claude-haiku-4-5"
    mock_urlopen.return_value = _make_urlopen_mock({
        "choices": [{"message": {"content": '{"location": "pub"}'}}]
    })

    call_llm("Hello")

    req = mock_urlopen.call_args[0][0]
    body = json.loads(req.data)
    assert body["model"] == "anthropic/claude-haiku-4-5"
    assert body["messages"][0]["role"] == "user"
    assert body["messages"][0]["content"] == "Hello"
    assert body["response_format"] == {"type": "json_object"}


@patch("simulation.llm.settings")
@patch("simulation.llm.urllib.request.urlopen")
def test_call_llm_raises_on_http_error(mock_urlopen, mock_settings):
    import urllib.error

    mock_settings.OPENROUTER_API_KEY = "test-key"
    mock_settings.LLM_MODEL = "anthropic/claude-haiku-4-5"
    mock_urlopen.side_effect = urllib.error.HTTPError(
        url=None, code=401, msg="Unauthorized", hdrs=None, fp=None
    )

    with pytest.raises(LLMError, match="401"):
        call_llm("Hello")


@patch("simulation.llm.settings")
def test_call_llm_raises_on_missing_api_key(mock_settings):
    mock_settings.OPENROUTER_API_KEY = ""

    with pytest.raises(LLMError, match="OPENROUTER_API_KEY"):
        call_llm("Hello")


# --- runner tests ---


@pytest.mark.django_db
@patch("simulation.pipeline.call_llm", side_effect=two_phase_responses(1))
def test_run_tick_creates_tick_record(_mock):
    make_location()
    tick = run_tick()
    assert Tick.objects.count() == 1
    assert tick.active is True


@pytest.mark.django_db
@patch("simulation.pipeline.call_llm", side_effect=two_phase_responses(2))
def test_run_tick_creates_agent_ticks(_mock):
    make_location()
    make_agent("Margaret")
    make_agent("Bernard")
    tick = run_tick()
    assert AgentTick.objects.filter(tick=tick).count() == 2


@pytest.mark.django_db
@patch("simulation.pipeline.call_llm", side_effect=two_phase_responses(1))
def test_run_tick_skips_inactive_agents(_mock):
    make_location()
    make_agent("Margaret", active=True)
    make_agent("Retired", active=False)
    tick = run_tick()
    assert AgentTick.objects.filter(tick=tick).count() == 1


@pytest.mark.django_db
@patch("simulation.pipeline.call_llm", side_effect=two_phase_responses(1))
def test_run_tick_advances_in_game_time(_mock, settings):
    make_location()
    base_time = tz.now()
    make_tick(in_game_time=base_time)
    tick = run_tick()
    expected = base_time + timedelta(minutes=settings.TICK_INTERVAL_MINUTES)
    assert abs((tick.in_game_time - expected).total_seconds()) < 1


@pytest.mark.django_db
@patch("simulation.pipeline.call_llm", side_effect=two_phase_responses(1))
def test_run_tick_uses_now_when_no_prior_tick(_mock, settings):
    make_location()
    tick = run_tick()
    assert tick.in_game_time.second == 0
    assert tick.in_game_time.microsecond == 0
    assert tick.in_game_time.minute % settings.TICK_INTERVAL_MINUTES == 0


@pytest.mark.django_db
@patch(
    "simulation.pipeline.call_llm",
    side_effect=two_phase_responses(
        1,
        phase1=json.dumps({
            "location": "nonexistent_slug",
            "intention": "Wandering around.",
        }),
        phase2=json.dumps({
            "activity": "Wandering",
            "inner_thought": "Lost.",
            "mood": "confused",
        }),
    ),
)
def test_run_tick_handles_invalid_location_slug(_mock):
    make_location()
    make_agent()
    tick = run_tick()
    at = AgentTick.objects.get(tick=tick)
    assert at.location is None
    assert at.activity == "Wandering"


@pytest.mark.django_db
def test_run_tick_handles_llm_error():
    make_location()
    make_agent("Good")
    make_agent("Bad")

    with patch(
        "simulation.pipeline.call_llm",
        side_effect=[
            LLMError("OpenRouter HTTP 500: Internal Server Error"),  # phase 1 Good
            VALID_LLM_RESPONSE,  # phase 1 Bad
            VALID_LLM_RESPONSE,  # phase 2 Bad
        ],
    ):
        tick = run_tick()

    assert AgentTick.objects.filter(tick=tick).count() == 1


@pytest.mark.django_db
def test_run_tick_activates_tick_even_with_partial_failure():
    make_location()
    make_agent("Good")
    make_agent("Bad")

    with patch(
        "simulation.pipeline.call_llm",
        side_effect=[
            LLMError("OpenRouter HTTP 500: Internal Server Error"),  # phase 1 Good
            VALID_LLM_RESPONSE,  # phase 1 Bad
            VALID_LLM_RESPONSE,  # phase 2 Bad
        ],
    ):
        tick = run_tick()

    assert tick.active is True
    assert AgentTick.objects.filter(tick=tick).count() == 1


@pytest.mark.django_db
@patch(
    "simulation.pipeline.call_llm",
    side_effect=[FENCED_LLM_RESPONSE, FENCED_LLM_RESPONSE],
)
def test_run_tick_handles_markdown_fenced_response(_mock):
    make_location()
    make_agent()
    tick = run_tick()
    at = AgentTick.objects.get(tick=tick)
    assert at.activity == "Reading the newspaper"
    assert at.mood == "peaceful"


@pytest.mark.django_db
@patch("simulation.pipeline.call_llm", side_effect=two_phase_responses(1))
def test_run_tick_stores_raw_prompts_and_responses(_mock):
    make_location()
    make_agent()
    tick = run_tick()
    at = AgentTick.objects.get(tick=tick)
    assert "LocationResolutionStep" in at.raw_prompts
    assert "ActivityGenerationStep" in at.raw_prompts
    assert len(at.raw_prompts["LocationResolutionStep"]) > 0
    assert len(at.raw_prompts["ActivityGenerationStep"]) > 0
    assert at.raw_responses["ActivityGenerationStep"] == VALID_LLM_RESPONSE


# --- abandoned tick recovery tests ---


@pytest.mark.django_db
def test_run_tick_resumes_partially_complete_abandoned_tick(settings):
    """Crash during Phase 2: agent A has AgentTick, agent B is missing. B should be resumed."""
    location = make_location()
    agent_a = make_agent("AgentA")
    agent_b = make_agent("AgentB")
    abandoned_time = tz.now() - timedelta(hours=1)
    abandoned = make_tick(in_game_time=abandoned_time, active=False)
    make_agent_tick(agent_a, abandoned, location=location)

    # Resume calls: Phase 1 + Phase 2 for agent B (2 calls)
    # New tick calls: Phase 1 A, Phase 1 B, Phase 2 A, Phase 2 B (4 calls)
    side_effects = two_phase_responses(1) + two_phase_responses(2)
    with patch("simulation.pipeline.call_llm", side_effect=side_effects):
        new_tick = run_tick()

    abandoned.refresh_from_db()
    assert abandoned.active is True
    assert AgentTick.objects.filter(tick=abandoned, agent=agent_b).exists()
    assert AgentTick.objects.filter(tick=abandoned).count() == 2

    expected = abandoned_time + timedelta(minutes=settings.TICK_INTERVAL_MINUTES)
    assert abs((new_tick.in_game_time - expected).total_seconds()) < 1


@pytest.mark.django_db
def test_run_tick_resumes_fully_incomplete_abandoned_tick(settings):
    """Crash during Phase 1: no AgentTick records at all. Full pipeline runs for all agents."""
    make_location()
    make_agent("AgentA")
    make_agent("AgentB")
    abandoned_time = tz.now() - timedelta(hours=1)
    abandoned = make_tick(in_game_time=abandoned_time, active=False)

    # Resume: Phase 1 A, Phase 1 B, Phase 2 A, Phase 2 B (4 calls)
    # New tick: same again (4 calls)
    side_effects = two_phase_responses(2) + two_phase_responses(2)
    with patch("simulation.pipeline.call_llm", side_effect=side_effects):
        new_tick = run_tick()

    abandoned.refresh_from_db()
    assert abandoned.active is True
    assert AgentTick.objects.filter(tick=abandoned).count() == 2

    expected = abandoned_time + timedelta(minutes=settings.TICK_INTERVAL_MINUTES)
    assert abs((new_tick.in_game_time - expected).total_seconds()) < 1


@pytest.mark.django_db
def test_run_tick_catchup_resumes_abandoned_tick(settings):
    """Catchup mode resumes an abandoned tick before jumping to ceil(now, interval)."""
    make_location()
    make_agent()
    abandoned = make_tick(in_game_time=tz.now() - timedelta(hours=2), active=False)

    # Resume: 2 calls; new tick: 2 calls
    with patch(
        "simulation.pipeline.call_llm",
        side_effect=two_phase_responses(1) + two_phase_responses(1),
    ):
        new_tick = run_tick(catchup=True)

    abandoned.refresh_from_db()
    assert abandoned.active is True
    expected = _ceil_to_interval(tz.now(), settings.TICK_INTERVAL_MINUTES)
    assert abs((new_tick.in_game_time - expected).total_seconds()) < 2


# --- daily plan tests ---


@pytest.mark.django_db
@patch("simulation.pipeline.call_llm", return_value=VALID_LLM_RESPONSE_WITH_PLAN)
def test_plan_generated_on_first_morning_tick(_mock, settings):
    settings.PLAN_HOUR = 6
    make_location()
    agent = make_agent()
    morning_time = tz.now().replace(hour=7, minute=0, second=0, microsecond=0)
    make_tick(in_game_time=morning_time - timedelta(minutes=15))
    run_tick()
    plan = DailyPlan.objects.filter(agent=agent).first()
    assert plan is not None
    assert plan.date == (morning_time + timedelta(minutes=15)).date()
    assert plan.plan == [
        "08:00 — Have breakfast at the harbour café",
        "11:00 — Visit Margaret at her cottage",
        "13:00 — Pick up a newspaper from the corner shop",
    ]


@pytest.mark.django_db
@patch("simulation.pipeline.call_llm", return_value=VALID_LLM_RESPONSE_WITH_PLAN)
def test_plan_not_generated_before_plan_hour(_mock, settings):
    settings.PLAN_HOUR = 6
    make_location()
    make_agent()
    early_time = tz.now().replace(hour=5, minute=15, second=0, microsecond=0)
    make_tick(in_game_time=early_time)
    run_tick()
    assert DailyPlan.objects.count() == 0


@pytest.mark.django_db
@patch("simulation.pipeline.call_llm", return_value=VALID_LLM_RESPONSE_WITH_PLAN)
def test_plan_not_regenerated_when_one_exists(_mock, settings):
    settings.PLAN_HOUR = 6
    make_location()
    agent = make_agent()
    morning_time = tz.now().replace(hour=7, minute=0, second=0, microsecond=0)
    prior_tick = make_tick(in_game_time=morning_time, active=True)
    DailyPlan.objects.create(
        agent=agent,
        date=morning_time.date(),
        plan=["Existing plan item"],
        generated_at_tick=prior_tick,
    )
    make_tick(in_game_time=morning_time + timedelta(minutes=15))
    run_tick()
    assert DailyPlan.objects.filter(agent=agent).count() == 1


@pytest.mark.django_db
@patch("simulation.pipeline.call_llm")
def test_plan_gracefully_skipped_on_invalid_llm_output(mock_llm, settings):
    settings.PLAN_HOUR = 6
    make_location()
    make_agent()
    mock_llm.return_value = json.dumps({
        "location": "harbour_cafe",
        "intention": "Having coffee",
        "activity": "Wandering",
        "inner_thought": "Hmm.",
        "mood": "confused",
        "daily_plan": "not a list",
    })
    morning_time = tz.now().replace(hour=7, minute=0, second=0, microsecond=0)
    make_tick(in_game_time=morning_time)
    run_tick()
    assert DailyPlan.objects.count() == 0


# --- _round_to_interval tests ---


def test_round_to_interval_rounds_down():
    dt = tz.now().replace(hour=10, minute=7, second=30, microsecond=0)
    result = _round_to_interval(dt, 15)
    assert result.hour == 10
    assert result.minute == 0
    assert result.second == 0


def test_round_to_interval_rounds_up():
    dt = tz.now().replace(hour=10, minute=8, second=0, microsecond=0)
    result = _round_to_interval(dt, 15)
    assert result.hour == 10
    assert result.minute == 15
    assert result.second == 0


def test_round_to_interval_on_exact_boundary():
    dt = tz.now().replace(hour=10, minute=15, second=0, microsecond=0)
    result = _round_to_interval(dt, 15)
    assert result.hour == 10
    assert result.minute == 15


def test_round_to_interval_clears_subseconds():
    dt = tz.now().replace(hour=10, minute=0, second=45, microsecond=123456)
    result = _round_to_interval(dt, 15)
    assert result.second == 0
    assert result.microsecond == 0


# --- _ceil_to_interval tests ---


def test_ceil_to_interval_rounds_up():
    dt = tz.now().replace(hour=10, minute=7, second=30, microsecond=0)
    result = _ceil_to_interval(dt, 15)
    assert result.hour == 10
    assert result.minute == 15
    assert result.second == 0


def test_ceil_to_interval_on_exact_boundary():
    dt = tz.now().replace(hour=10, minute=15, second=0, microsecond=0)
    result = _ceil_to_interval(dt, 15)
    assert result.hour == 10
    assert result.minute == 15


def test_ceil_to_interval_never_rounds_back():
    dt = tz.now().replace(hour=10, minute=1, second=0, microsecond=0)
    result = _ceil_to_interval(dt, 15)
    assert result >= dt


# --- catchup tests ---


@pytest.mark.django_db
@patch("simulation.pipeline.call_llm", side_effect=two_phase_responses(1))
def test_run_tick_catchup_jumps_to_ceil_now(_mock, settings):
    make_location()
    old_time = tz.now() - timedelta(hours=5)
    make_tick(in_game_time=old_time, active=True)
    tick = run_tick(catchup=True)
    expected = _ceil_to_interval(tz.now(), settings.TICK_INTERVAL_MINUTES)
    assert abs((tick.in_game_time - expected).total_seconds()) < 2


@pytest.mark.django_db
def test_run_tick_catchup_noop_when_sim_is_ahead(settings):
    make_location()
    future_time = tz.now() + timedelta(hours=1)
    existing_tick = make_tick(in_game_time=future_time, active=True)
    with pytest.raises(SimulationAlreadyUpToDate) as exc_info:
        run_tick(catchup=True)
    assert exc_info.value.tick.id == existing_tick.id
    assert Tick.objects.count() == 1


@pytest.mark.django_db
def test_run_tick_catchup_noop_when_ceiled_equals_last_tick(settings):
    make_location()
    ceiled_now = _ceil_to_interval(tz.now(), settings.TICK_INTERVAL_MINUTES)
    existing_tick = make_tick(in_game_time=ceiled_now, active=True)
    with pytest.raises(SimulationAlreadyUpToDate) as exc_info:
        run_tick(catchup=True)
    assert exc_info.value.tick.id == existing_tick.id
    assert Tick.objects.count() == 1
