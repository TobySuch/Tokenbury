import pytest
from world.models import Location


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
