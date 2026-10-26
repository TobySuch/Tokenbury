from django.conf import settings
from django.db.models import Prefetch
from django.utils import timezone as tz
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from config.cache import cached
from config.http import IMMUTABLE, LIVE, cache_public
from world.models import Agent, AgentTick, Banner, Instance, Location, Tick
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


def _tick_detail_data(pk):
    # raw_prompts/raw_responses are large debug blobs the serializer never uses.
    agent_states = AgentTick.objects.defer(
        "raw_prompts", "raw_responses"
    ).select_related("agent", "location")
    tick = Tick.objects.prefetch_related(
        Prefetch("agent_states", queryset=agent_states)
    ).get(pk=pk)
    return TickDetailSerializer(tick).data


def _cached_tick_detail(tick):
    """Serialise a tick, caching it once it is active and so immutable."""
    if not tick.active:
        return _tick_detail_data(tick.pk)
    return cached(f"tick:{tick.pk}", IMMUTABLE, lambda: _tick_detail_data(tick.pk))


@api_view(["GET"])
def health(request):
    return Response({"status": "ok", "message": "Tokenbury is alive 🌊"})


@api_view(["GET"])
def active_instance(request):
    instance = _active_instance()
    if instance is None:
        return Response(status=status.HTTP_404_NOT_FOUND)
    return cache_public(
        Response(InstanceSerializer(instance, context={"request": request}).data),
        LIVE,
    )


@api_view(["GET"])
def active_banner(request):
    site = request.query_params.get("site", Banner.Site.TOWN)
    if site not in (Banner.Site.TOWN, Banner.Site.WEREWOLF):
        return Response(
            {"detail": "site must be 'town' or 'werewolf'"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    banner = Banner.objects.filter(
        active=True, site__in=[site, Banner.Site.BOTH]
    ).first()
    if banner is None:
        return Response(status=status.HTTP_404_NOT_FOUND)
    return cache_public(Response(BannerSerializer(banner).data), LIVE)


@api_view(["GET"])
def agent_detail(request, pk):
    try:
        agent = Agent.objects.get(pk=pk)
    except Agent.DoesNotExist:
        return Response(status=status.HTTP_404_NOT_FOUND)
    return cache_public(Response(AgentDetailSerializer(agent).data), LIVE)


@api_view(["GET"])
def locations(request):
    instance = _active_instance()
    qs = (
        Location.objects.filter(instance=instance)
        if instance
        else Location.objects.none()
    )
    return cache_public(Response(LocationSerializer(qs, many=True).data), LIVE)


@api_view(["GET"])
def tick_list(request):
    instance = _active_instance()
    qs = Tick.objects.filter(instance=instance) if instance else Tick.objects.none()
    qs = _apply_live_filter(qs)
    date_str = request.query_params.get("date")
    max_age = LIVE
    if date_str:
        latest = qs.filter(active=True).only("in_game_time").first()
        if latest and date_str < latest.in_game_time.date().isoformat():
            max_age = IMMUTABLE
        qs = qs.filter(in_game_time__date=date_str)
    return cache_public(Response(TickListSerializer(qs, many=True).data), max_age)


@api_view(["GET"])
def tick_days(request):
    instance = _active_instance()
    qs = Tick.objects.filter(instance=instance) if instance else Tick.objects.none()
    qs = _apply_live_filter(qs)
    dates = qs.dates("in_game_time", "day", order="ASC")
    return cache_public(Response([d.isoformat() for d in dates]), LIVE)


@api_view(["GET"])
def tick_detail(request, pk):
    tick = _apply_live_filter(Tick.objects.only("id", "active")).filter(pk=pk).first()
    if tick is None:
        return Response(status=status.HTTP_404_NOT_FOUND)
    return cache_public(
        Response(_cached_tick_detail(tick)), IMMUTABLE if tick.active else LIVE
    )


@api_view(["GET"])
def tick_latest(request):
    instance = _active_instance()
    qs = Tick.objects.filter(active=True)
    if instance:
        qs = qs.filter(instance=instance)
    qs = _apply_live_filter(qs)
    latest = qs.only("id", "active").first()
    if latest is None:
        return Response(status=status.HTTP_404_NOT_FOUND)

    last_tick_id = request.query_params.get("last_tick_id")
    if last_tick_id is not None:
        try:
            if int(last_tick_id) == latest.id:
                return Response(status=status.HTTP_304_NOT_MODIFIED)
        except ValueError:
            pass

    return cache_public(Response(_cached_tick_detail(latest)), LIVE)
