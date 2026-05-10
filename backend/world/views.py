from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status

from world.models import Location, Tick
from world.serializers import (
    LocationSerializer,
    TickDetailSerializer,
    TickListSerializer,
)


@api_view(["GET"])
def health(request):
    return Response({"status": "ok", "message": "Tokenbury is alive 🌊"})


@api_view(["GET"])
def locations(request):
    return Response(LocationSerializer(Location.objects.all(), many=True).data)


@api_view(["GET"])
def tick_list(request):
    return Response(TickListSerializer(Tick.objects.all(), many=True).data)


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
    tick = Tick.objects.prefetch_related(
        "agent_states__agent", "agent_states__location"
    ).first()
    if tick is None:
        return Response(status=status.HTTP_404_NOT_FOUND)
    return Response(TickDetailSerializer(tick).data)
