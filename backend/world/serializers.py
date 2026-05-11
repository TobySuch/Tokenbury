from rest_framework import serializers
from world.models import Agent, AgentTick, DailyPlan, Location, Tick


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
    agent_sprite_url = serializers.SerializerMethodField()
    location_slug = serializers.SlugRelatedField(
        source="location", slug_field="slug", read_only=True
    )

    def get_agent_sprite_url(self, obj):
        if obj.agent.sprite:
            return obj.agent.sprite.url
        return None

    class Meta:
        model = AgentTick
        fields = [
            "agent_id",
            "agent_name",
            "agent_sprite_url",
            "location_slug",
            "activity",
            "mood",
            "inner_thought",
        ]


class AgentDetailSerializer(serializers.ModelSerializer):
    sprite_url = serializers.SerializerMethodField()
    todays_plan = serializers.SerializerMethodField()

    def get_sprite_url(self, obj):
        if obj.sprite:
            return obj.sprite.url
        return None

    def get_todays_plan(self, obj):
        latest_tick = Tick.objects.filter(active=True).only("in_game_time").first()
        if not latest_tick:
            return None
        today = latest_tick.in_game_time.date()
        plan = DailyPlan.objects.filter(agent=obj, date=today).first()
        return plan.plan if plan else None

    class Meta:
        model = Agent
        fields = ["id", "name", "bio", "sprite_url", "todays_plan"]


class TickListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tick
        fields = ["id", "in_game_time", "created_at"]


class TickDetailSerializer(serializers.ModelSerializer):
    agent_states = AgentTickSerializer(many=True, read_only=True)

    class Meta:
        model = Tick
        fields = ["id", "in_game_time", "created_at", "agent_states"]
