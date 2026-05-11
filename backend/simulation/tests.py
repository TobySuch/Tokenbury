import json
from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest
from django.utils import timezone as tz

from world.models import Agent, AgentTick, DailyPlan, Location, Tick

from simulation.llm import LLMError, call_llm
from simulation.prompts import build_agent_prompt
from simulation.runner import _extract_json, _normalise, run_tick


# --- factories ---


def make_agent(name="Margaret", active=True):
    return Agent.objects.create(
        name=name,
        bio=f"{name} is a retired teacher who loves the sea.",
        sprite="sprites/margaret.png",
        active=active,
    )


def make_location(slug="harbour_cafe", name="Harbour Café"):
    return Location.objects.create(
        slug=slug,
        name=name,
        description="A cosy café overlooking the harbour.",
        bbox_x1=0.0,
        bbox_y1=0.0,
        bbox_x2=100.0,
        bbox_y2=100.0,
    )


def make_tick(in_game_time=None, active=False):
    if in_game_time is None:
        in_game_time = tz.now()
    return Tick.objects.create(in_game_time=in_game_time, active=active)


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


VALID_LLM_RESPONSE = json.dumps({
    "location": "harbour_cafe",
    "activity": "Reading the newspaper",
    "inner_thought": "I wonder if the boats are back.",
    "mood": "peaceful",
})

VALID_LLM_RESPONSE_WITH_PLAN = json.dumps({
    "location": "harbour_cafe",
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


# --- prompt tests ---


@pytest.mark.django_db
def test_prompt_contains_agent_bio():
    agent = make_agent()
    tick = make_tick()
    location = make_location()
    prompt = build_agent_prompt(agent, tick, [], [], [location])
    assert agent.bio in prompt


@pytest.mark.django_db
def test_prompt_contains_previous_ticks():
    agent = make_agent()
    location = make_location()
    earlier_tick = make_tick(tz.now() - timedelta(hours=1))
    at = make_agent_tick(
        agent, earlier_tick, location=location, activity="Buying bread"
    )
    current_tick = make_tick()
    prompt = build_agent_prompt(agent, current_tick, [at], [], [location])
    assert "Buying bread" in prompt


@pytest.mark.django_db
def test_prompt_empty_history_when_no_prior_ticks():
    agent = make_agent()
    tick = make_tick()
    location = make_location()
    prompt = build_agent_prompt(agent, tick, [], [], [location])
    assert "start of your day" in prompt


@pytest.mark.django_db
def test_prompt_contains_valid_locations():
    agent = make_agent()
    tick = make_tick()
    loc1 = make_location(slug="harbour_cafe", name="Harbour Café")
    loc2 = make_location(slug="pub", name="The Pub")
    prompt = build_agent_prompt(agent, tick, [], [], [loc1, loc2])
    assert "harbour_cafe" in prompt
    assert "pub" in prompt


@pytest.mark.django_db
def test_prompt_contains_world_state():
    agent = make_agent()
    tick = make_tick()
    location = make_location()
    world_state = [
        {"name": "Bernard", "location": "harbour_cafe", "activity": "Fishing"}
    ]
    prompt = build_agent_prompt(agent, tick, [], world_state, [location])
    assert "Bernard" in prompt
    assert "Fishing" in prompt


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
@patch("simulation.runner.call_llm", return_value=VALID_LLM_RESPONSE)
def test_run_tick_creates_tick_record(_mock):
    make_location()
    tick = run_tick()
    assert Tick.objects.count() == 1
    assert tick.active is True


@pytest.mark.django_db
@patch("simulation.runner.call_llm", return_value=VALID_LLM_RESPONSE)
def test_run_tick_creates_agent_ticks(_mock):
    make_location()
    make_agent("Margaret")
    make_agent("Bernard")
    tick = run_tick()
    assert AgentTick.objects.filter(tick=tick).count() == 2


@pytest.mark.django_db
@patch("simulation.runner.call_llm", return_value=VALID_LLM_RESPONSE)
def test_run_tick_skips_inactive_agents(_mock):
    make_location()
    make_agent("Margaret", active=True)
    make_agent("Retired", active=False)
    tick = run_tick()
    assert AgentTick.objects.filter(tick=tick).count() == 1


@pytest.mark.django_db
@patch("simulation.runner.call_llm", return_value=VALID_LLM_RESPONSE)
def test_run_tick_advances_in_game_time(_mock, settings):
    make_location()
    base_time = tz.now()
    Tick.objects.create(in_game_time=base_time)
    tick = run_tick()
    expected = base_time + timedelta(minutes=settings.TICK_INTERVAL_MINUTES)
    assert abs((tick.in_game_time - expected).total_seconds()) < 1


@pytest.mark.django_db
@patch("simulation.runner.call_llm", return_value=VALID_LLM_RESPONSE)
def test_run_tick_uses_now_when_no_prior_tick(_mock):
    make_location()
    before = tz.now()
    tick = run_tick()
    after = tz.now()
    assert before <= tick.in_game_time <= after


@pytest.mark.django_db
@patch(
    "simulation.runner.call_llm",
    return_value=json.dumps({
        "location": "nonexistent_slug",
        "activity": "Wandering",
        "inner_thought": "Lost.",
        "mood": "confused",
    }),
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

    call_count = 0

    def side_effect(prompt):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise LLMError("OpenRouter HTTP 500: Internal Server Error")
        return VALID_LLM_RESPONSE

    with patch("simulation.runner.call_llm", side_effect=side_effect):
        tick = run_tick()

    assert AgentTick.objects.filter(tick=tick).count() == 1


@pytest.mark.django_db
def test_run_tick_activates_tick_even_with_partial_failure():
    make_location()
    make_agent("Good")
    make_agent("Bad")

    call_count = 0

    def side_effect(prompt):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise LLMError("OpenRouter HTTP 500: Internal Server Error")
        return VALID_LLM_RESPONSE

    with patch("simulation.runner.call_llm", side_effect=side_effect):
        tick = run_tick()

    assert tick.active is True
    assert AgentTick.objects.filter(tick=tick).count() == 1


@pytest.mark.django_db
@patch("simulation.runner.call_llm", return_value=FENCED_LLM_RESPONSE)
def test_run_tick_handles_markdown_fenced_response(_mock):
    make_location()
    make_agent()
    tick = run_tick()
    at = AgentTick.objects.get(tick=tick)
    assert at.activity == "Reading the newspaper"
    assert at.mood == "peaceful"


@pytest.mark.django_db
@patch("simulation.runner.call_llm", return_value=VALID_LLM_RESPONSE)
def test_run_tick_stores_raw_prompt_and_response(_mock):
    make_location()
    make_agent()
    tick = run_tick()
    at = AgentTick.objects.get(tick=tick)
    assert len(at.raw_prompt) > 0
    assert at.raw_response == VALID_LLM_RESPONSE


# --- daily plan tests ---


@pytest.mark.django_db
@patch("simulation.runner.call_llm", return_value=VALID_LLM_RESPONSE_WITH_PLAN)
def test_plan_generated_on_first_morning_tick(_mock, settings):
    settings.PLAN_HOUR = 6
    make_location()
    agent = make_agent()
    morning_time = tz.now().replace(hour=7, minute=0, second=0, microsecond=0)
    Tick.objects.create(in_game_time=morning_time - timedelta(minutes=15))
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
@patch("simulation.runner.call_llm", return_value=VALID_LLM_RESPONSE_WITH_PLAN)
def test_plan_not_generated_before_plan_hour(_mock, settings):
    settings.PLAN_HOUR = 6
    make_location()
    make_agent()
    # Tick at 05:30 — before PLAN_HOUR
    early_time = tz.now().replace(hour=5, minute=15, second=0, microsecond=0)
    Tick.objects.create(in_game_time=early_time)
    run_tick()
    assert DailyPlan.objects.count() == 0


@pytest.mark.django_db
@patch("simulation.runner.call_llm", return_value=VALID_LLM_RESPONSE_WITH_PLAN)
def test_plan_not_regenerated_when_one_exists(_mock, settings):
    settings.PLAN_HOUR = 6
    make_location()
    agent = make_agent()
    morning_time = tz.now().replace(hour=7, minute=0, second=0, microsecond=0)
    prior_tick = Tick.objects.create(in_game_time=morning_time, active=True)
    DailyPlan.objects.create(
        agent=agent,
        date=morning_time.date(),
        plan=["Existing plan item"],
        generated_at_tick=prior_tick,
    )
    Tick.objects.create(in_game_time=morning_time + timedelta(minutes=15))
    run_tick()
    assert DailyPlan.objects.filter(agent=agent).count() == 1


@pytest.mark.django_db
def test_existing_plan_injected_into_prompt():
    agent = make_agent()
    tick = make_tick()
    location = make_location()
    plan = ["Buy fish from the harbour", "Visit Margaret"]
    prompt = build_agent_prompt(agent, tick, [], [], [location], daily_plan=plan)
    assert "Buy fish from the harbour" in prompt
    assert "Visit Margaret" in prompt
    assert "Your Plan for Today" in prompt


@pytest.mark.django_db
def test_needs_plan_adds_daily_plan_to_instructions():
    agent = make_agent()
    tick = make_tick()
    location = make_location()
    prompt = build_agent_prompt(agent, tick, [], [], [location], needs_plan=True)
    assert "daily_plan" in prompt


@pytest.mark.django_db
def test_no_plan_section_when_plan_is_none():
    agent = make_agent()
    tick = make_tick()
    location = make_location()
    prompt = build_agent_prompt(agent, tick, [], [], [location])
    assert "Your Plan for Today" not in prompt


@pytest.mark.django_db
@patch("simulation.runner.call_llm")
def test_plan_gracefully_skipped_on_invalid_llm_output(mock_llm, settings):
    settings.PLAN_HOUR = 6
    make_location()
    make_agent()
    mock_llm.return_value = json.dumps({
        "location": "harbour_cafe",
        "activity": "Wandering",
        "inner_thought": "Hmm.",
        "mood": "confused",
        "daily_plan": "not a list",
    })
    morning_time = tz.now().replace(hour=7, minute=0, second=0, microsecond=0)
    Tick.objects.create(in_game_time=morning_time)
    run_tick()
    assert DailyPlan.objects.count() == 0
