from django.conf import settings
from django.utils import timezone as tz
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status

from world.models import Agent, Banner, Instance, Location, Tick
from world.serializers import (
    AgentDetailSerializer,
    BannerSerializer,
    InstanceSerializer,
    LocationSerializer,
    TickDetailSerializer,
    TickListSerializer,
)


def _active_instance():
    return Instance.objects.filter(active=True).first()


def _apply_live_filter(qs):
    if settings.API_HIDE_FUTURE_TICKS:
        return qs.filter(in_game_time__lte=tz.now())
    return qs


@api_view(["GET"])
def health(request):
    return Response({"status": "ok", "message": "Tokenbury is alive 🌊"})


@api_view(["GET"])
def active_instance(request):
    instance = _active_instance()
    if instance is None:
        return Response(status=status.HTTP_404_NOT_FOUND)
    return Response(InstanceSerializer(instance, context={"request": request}).data)


@api_view(["GET"])
def active_banner(request):
    banner = Banner.objects.filter(active=True).first()
    if banner is None:
        return Response(status=status.HTTP_404_NOT_FOUND)
    return Response(BannerSerializer(banner).data)


@api_view(["GET"])
def agent_detail(request, pk):
    try:
        agent = Agent.objects.get(pk=pk)
    except Agent.DoesNotExist:
        return Response(status=status.HTTP_404_NOT_FOUND)
    return Response(AgentDetailSerializer(agent).data)


@api_view(["GET"])
def locations(request):
    instance = _active_instance()
    qs = (
        Location.objects.filter(instance=instance)
        if instance
        else Location.objects.none()
    )
    return Response(LocationSerializer(qs, many=True).data)


@api_view(["GET"])
def tick_list(request):
    instance = _active_instance()
    qs = Tick.objects.filter(instance=instance) if instance else Tick.objects.none()
    qs = _apply_live_filter(qs)
    date_str = request.query_params.get("date")
    if date_str:
        qs = qs.filter(in_game_time__date=date_str)
    return Response(TickListSerializer(qs, many=True).data)


@api_view(["GET"])
def tick_days(request):
    instance = _active_instance()
    qs = Tick.objects.filter(instance=instance) if instance else Tick.objects.none()
    qs = _apply_live_filter(qs)
    dates = qs.dates("in_game_time", "day", order="ASC")
    return Response([d.isoformat() for d in dates])


@api_view(["GET"])
def tick_detail(request, pk):
    qs = _apply_live_filter(
        Tick.objects.prefetch_related("agent_states__agent", "agent_states__location")
    )
    try:
        tick = qs.get(pk=pk)
    except Tick.DoesNotExist:
        return Response(status=status.HTTP_404_NOT_FOUND)
    return Response(TickDetailSerializer(tick).data)


@api_view(["GET"])
def tick_latest(request):
    instance = _active_instance()
    qs = Tick.objects.filter(active=True)
    if instance:
        qs = qs.filter(instance=instance)
    qs = _apply_live_filter(qs)
    latest = qs.only("id").first()
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
