import pytest
from world.models import Agent, AgentTick, DailyPlan, Instance, Location, Tick


def make_instance(name="Test Instance", slug="test-instance", active=True):
    inst, _ = Instance.objects.get_or_create(
        slug=slug,
        defaults={"name": name, "map_image": "maps/test.png", "active": active},
    )
    return inst


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
        instance=make_instance(),
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


def make_agent(name="Margaret", instance=None):
    if instance is None:
        instance = make_instance()
    return Agent.objects.create(
        instance=instance,
        name=name,
        bio="A retired teacher.",
        sprite="sprites/margaret.png",
        active=True,
    )


def make_location(instance=None):
    if instance is None:
        instance = make_instance()
    return Location.objects.create(
        instance=instance,
        slug="harbour_cafe",
        name="Harbour Café",
        description="A cosy café.",
        bbox_x1=0.0,
        bbox_y1=0.0,
        bbox_x2=100.0,
        bbox_y2=100.0,
    )


def make_tick(in_game_time="2024-01-01T09:00:00Z", active=False, instance=None):
    if instance is None:
        instance = make_instance()
    return Tick.objects.create(
        in_game_time=in_game_time, active=active, instance=instance
    )


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


@pytest.mark.django_db
def test_tick_list_filtered_by_date(client):
    make_tick("2024-01-01T09:00:00Z")
    make_tick("2024-01-02T09:00:00Z")
    response = client.get("/api/ticks/?date=2024-01-01")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["in_game_time"].startswith("2024-01-01")


@pytest.mark.django_db
def test_tick_list_date_filter_no_match(client):
    make_tick("2024-01-01T09:00:00Z")
    response = client.get("/api/ticks/?date=2024-01-02")
    assert response.status_code == 200
    assert response.json() == []


# --- /api/ticks/days/ ---


@pytest.mark.django_db
def test_tick_days_empty(client):
    response = client.get("/api/ticks/days/")
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.django_db
def test_tick_days_returns_sorted_dates(client):
    make_tick("2024-01-02T09:00:00Z")
    make_tick("2024-01-01T10:00:00Z")
    make_tick("2024-01-01T09:00:00Z")
    response = client.get("/api/ticks/days/")
    assert response.status_code == 200
    data = response.json()
    assert data == ["2024-01-01", "2024-01-02"]


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


# --- /api/agents/<pk>/ ---


@pytest.mark.django_db
def test_agent_detail_not_found(client):
    response = client.get("/api/agents/999/")
    assert response.status_code == 404


@pytest.mark.django_db
def test_agent_detail_returns_bio(client):
    agent = make_agent("Margaret")
    response = client.get(f"/api/agents/{agent.pk}/")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == agent.pk
    assert data["name"] == "Margaret"
    assert data["bio"] == "A retired teacher."
    assert data["todays_plan"] is None


@pytest.mark.django_db
def test_agent_detail_returns_todays_plan(client):
    agent = make_agent()
    tick = make_tick(in_game_time="2024-01-01T09:00:00Z", active=True)
    DailyPlan.objects.create(
        agent=agent,
        date="2024-01-01",
        plan=["Morning walk", "Coffee at café"],
        generated_at_tick=tick,
    )
    response = client.get(f"/api/agents/{agent.pk}/")
    assert response.status_code == 200
    data = response.json()
    assert data["todays_plan"] == ["Morning walk", "Coffee at café"]


@pytest.mark.django_db
def test_agent_detail_no_plan_for_today_returns_none(client):
    agent = make_agent()
    tick = make_tick(in_game_time="2024-01-02T09:00:00Z", active=True)
    DailyPlan.objects.create(
        agent=agent,
        date="2024-01-01",
        plan=["Yesterday's plan"],
        generated_at_tick=tick,
    )
    response = client.get(f"/api/agents/{agent.pk}/")
    assert response.status_code == 200
    assert response.json()["todays_plan"] is None


# --- /api/instance/ ---


@pytest.mark.django_db
def test_instance_endpoint_404_when_no_instance(client):
    response = client.get("/api/instance/")
    assert response.status_code == 404


@pytest.mark.django_db
def test_instance_endpoint_404_when_no_active_instance(client):
    Instance.objects.create(
        name="Inactive", slug="inactive", map_image="maps/test.png", active=False
    )
    response = client.get("/api/instance/")
    assert response.status_code == 404


@pytest.mark.django_db
def test_instance_endpoint_returns_active_instance(client):
    make_instance(name="Tokenbury-on-Sea", slug="tokenbury-on-sea")
    response = client.get("/api/instance/")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Tokenbury-on-Sea"
    assert data["slug"] == "tokenbury-on-sea"
    assert "map_image_url" in data


@pytest.mark.django_db
def test_locations_filtered_by_active_instance(client):
    active_inst = make_instance()
    inactive_inst = Instance.objects.create(
        name="Other Instance",
        slug="other-instance",
        map_image="maps/test.png",
        active=False,
    )
    make_location(instance=active_inst)
    Location.objects.create(
        instance=inactive_inst,
        slug="harbour_cafe",
        name="Other Café",
        description="Not visible.",
        bbox_x1=0.0,
        bbox_y1=0.0,
        bbox_x2=100.0,
        bbox_y2=100.0,
    )
    response = client.get("/api/locations/")
    assert response.status_code == 200
    assert len(response.json()) == 1
