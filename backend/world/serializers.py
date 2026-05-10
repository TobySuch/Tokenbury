from rest_framework import serializers
from world.models import AgentTick, Location, Tick


class LocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Location
        fields = [
            "id",
            "slug",
            "name",
            "description",
            "bbox_x1",
            "bbox_y1",
            "bbox_x2",
            "bbox_y2",
        ]


class AgentTickSerializer(serializers.ModelSerializer):
    agent_id = serializers.IntegerField(source="agent.id")
    agent_name = serializers.CharField(source="agent.name")
    location_slug = serializers.SlugRelatedField(
        source="location", slug_field="slug", read_only=True
    )

    class Meta:
        model = AgentTick
        fields = [
            "agent_id",
            "agent_name",
            "location_slug",
            "activity",
            "mood",
            "inner_thought",
        ]


class TickListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tick
        fields = ["id", "in_game_time", "created_at"]


class TickDetailSerializer(serializers.ModelSerializer):
    agent_states = AgentTickSerializer(many=True, read_only=True)

    class Meta:
        model = Tick
        fields = ["id", "in_game_time", "created_at", "agent_states"]
