import pytest
from world.models import Agent, AgentTick, DailyPlan, Location, Tick


@pytest.mark.django_db
def test_health_check(client):
    response = client.get("/api/health/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


@pytest.mark.django_db
def test_locations_empty(client):
    response = client.get("/api/locations/")
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.django_db
def test_locations_returns_location(client):
    Location.objects.create(
        slug="harbour_cafe",
        name="Harbour Café",
        description="A cosy café overlooking the harbour.",
        bbox_x1=100.0,
        bbox_y1=200.0,
        bbox_x2=300.0,
        bbox_y2=400.0,
    )
    response = client.get("/api/locations/")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    loc = data[0]
    assert loc["slug"] == "harbour_cafe"
    assert loc["name"] == "Harbour Café"
    assert loc["description"] == "A cosy café overlooking the harbour."
    assert loc["bbox_x1"] == 100.0
    assert loc["bbox_y1"] == 200.0
    assert loc["bbox_x2"] == 300.0
    assert loc["bbox_y2"] == 400.0


@pytest.mark.django_db
def test_location_str():
    loc = Location(name="The Pub")
    assert str(loc) == "The Pub"


# --- helpers ---


def make_agent(name="Margaret"):
    return Agent.objects.create(
        name=name,
        bio="A retired teacher.",
        sprite="sprites/margaret.png",
        active=True,
    )


def make_location():
    return Location.objects.create(
        slug="harbour_cafe",
        name="Harbour Café",
        description="A cosy café.",
        bbox_x1=0.0,
        bbox_y1=0.0,
        bbox_x2=100.0,
        bbox_y2=100.0,
    )


def make_tick(in_game_time="2024-01-01T09:00:00Z", active=False):
    return Tick.objects.create(in_game_time=in_game_time, active=active)


# --- Tick model ---


@pytest.mark.django_db
def test_tick_str():
    tick = make_tick()
    assert "Tick" in str(tick)


@pytest.mark.django_db
def test_daily_plan_str():
    agent = make_agent()
    tick = make_tick()
    plan = DailyPlan.objects.create(
        agent=agent,
        date="2024-01-01",
        plan=["Have breakfast"],
        generated_at_tick=tick,
    )
    assert str(plan) == "Margaret's plan for 2024-01-01"


# --- /api/ticks/ ---


@pytest.mark.django_db
def test_tick_list_empty(client):
    response = client.get("/api/ticks/")
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.django_db
def test_tick_list_returns_ticks(client):
    make_tick("2024-01-01T09:00:00Z")
    make_tick("2024-01-01T10:00:00Z")
    response = client.get("/api/ticks/")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert "in_game_time" in data[0]
    assert "agent_states" not in data[0]


# --- /api/ticks/<id>/ ---


@pytest.mark.django_db
def test_tick_detail_not_found(client):
    response = client.get("/api/ticks/999/")
    assert response.status_code == 404


@pytest.mark.django_db
def test_tick_detail_no_agents(client):
    tick = make_tick()
    response = client.get(f"/api/ticks/{tick.pk}/")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == tick.pk
    assert data["agent_states"] == []


@pytest.mark.django_db
def test_tick_detail_with_agent_state(client):
    tick = make_tick()
    agent = make_agent()
    location = make_location()
    AgentTick.objects.create(
        agent=agent,
        tick=tick,
        location=location,
        activity="Having coffee",
        inner_thought="Feeling peaceful",
        mood="content",
    )
    response = client.get(f"/api/ticks/{tick.pk}/")
    assert response.status_code == 200
    data = response.json()
    assert len(data["agent_states"]) == 1
    state = data["agent_states"][0]
    assert state["agent_name"] == "Margaret"
    assert state["location_slug"] == "harbour_cafe"
    assert state["activity"] == "Having coffee"
    assert state["mood"] == "content"
    assert state["inner_thought"] == "Feeling peaceful"


@pytest.mark.django_db
def test_tick_detail_null_location(client):
    tick = make_tick()
    agent = make_agent()
    AgentTick.objects.create(
        agent=agent,
        tick=tick,
        location=None,
        activity="Wandering",
        inner_thought="Lost in thought",
        mood="pensive",
    )
    response = client.get(f"/api/ticks/{tick.pk}/")
    assert response.status_code == 200
    state = response.json()["agent_states"][0]
    assert state["location_slug"] is None


# --- /api/ticks/latest/ ---


@pytest.mark.django_db
def test_tick_latest_not_found(client):
    response = client.get("/api/ticks/latest/")
    assert response.status_code == 404


@pytest.mark.django_db
def test_tick_latest_returns_most_recent(client):
    make_tick("2024-01-01T08:00:00Z", active=True)
    latest = make_tick("2024-01-01T10:00:00Z", active=True)
    response = client.get("/api/ticks/latest/")
    assert response.status_code == 200
    assert response.json()["id"] == latest.pk


@pytest.mark.django_db
def test_tick_latest_304_when_id_matches(client):
    tick = make_tick(active=True)
    response = client.get(f"/api/ticks/latest/?last_tick_id={tick.pk}")
    assert response.status_code == 304


@pytest.mark.django_db
def test_tick_latest_200_when_id_differs(client):
    old_tick = make_tick("2024-01-01T08:00:00Z", active=True)
    latest = make_tick("2024-01-01T10:00:00Z", active=True)
    response = client.get(f"/api/ticks/latest/?last_tick_id={old_tick.pk}")
    assert response.status_code == 200
    assert response.json()["id"] == latest.pk


@pytest.mark.django_db
def test_tick_latest_200_when_id_invalid(client):
    make_tick(active=True)
    response = client.get("/api/ticks/latest/?last_tick_id=notanint")
    assert response.status_code == 200


@pytest.mark.django_db
def test_tick_latest_404_when_no_ticks_regardless_of_param(client):
    response = client.get("/api/ticks/latest/?last_tick_id=1")
    assert response.status_code == 404


@pytest.mark.django_db
def test_tick_latest_skips_inactive_tick(client):
    make_tick(active=False)
    response = client.get("/api/ticks/latest/")
    assert response.status_code == 404
