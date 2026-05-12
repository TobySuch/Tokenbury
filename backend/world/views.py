from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status

from world.models import Agent, Location, Tick
from world.serializers import (
    AgentDetailSerializer,
    LocationSerializer,
    TickDetailSerializer,
    TickListSerializer,
)


@api_view(["GET"])
def health(request):
    return Response({"status": "ok", "message": "Tokenbury is alive 🌊"})


@api_view(["GET"])
def agent_detail(request, pk):
    try:
        agent = Agent.objects.get(pk=pk)
    except Agent.DoesNotExist:
        return Response(status=status.HTTP_404_NOT_FOUND)
    return Response(AgentDetailSerializer(agent).data)


@api_view(["GET"])
def locations(request):
    return Response(LocationSerializer(Location.objects.all(), many=True).data)


@api_view(["GET"])
def tick_list(request):
    qs = Tick.objects.all()
    date_str = request.query_params.get("date")
    if date_str:
        qs = qs.filter(in_game_time__date=date_str)
    return Response(TickListSerializer(qs, many=True).data)


@api_view(["GET"])
def tick_days(request):
    dates = Tick.objects.dates("in_game_time", "day", order="ASC")
    return Response([d.isoformat() for d in dates])


@api_view(["GET"])
def tick_detail(request, pk):
    try:
        tick = Tick.objects.prefetch_related(
            "agent_states__agent", "agent_states__location"
        ).get(pk=pk)
    except Tick.DoesNotExist:
        return Response(status=status.HTTP_404_NOT_FOUND)
    return Response(TickDetailSerializer(tick).data)


@api_view(["GET"])
def tick_latest(request):
    latest = Tick.objects.filter(active=True).only("id").first()
    if latest is None:
        return Response(status=status.HTTP_404_NOT_FOUND)

    last_tick_id = request.query_params.get("last_tick_id")
    if last_tick_id is not None:
        try:
            if int(last_tick_id) == latest.id:
                return Response(status=status.HTTP_304_NOT_MODIFIED)
        except ValueError:
            pass

    tick = Tick.objects.prefetch_related(
        "agent_states__agent", "agent_states__location"
    ).get(pk=latest.id)
    return Response(TickDetailSerializer(tick).data)
