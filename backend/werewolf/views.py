from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from werewolf.beats import build_beats
from werewolf.models import Game
from werewolf.notes import notes_as_of
from werewolf.serializers import GameSerializer, PlayerSerializer


def _int_param(request, name):
    try:
        return int(request.query_params[name])
    except KeyError, ValueError:
        return None


def _published():
    return Game.objects.filter(published=True)


def _game_or_404(pk):
    return _published().filter(pk=pk).first()


@api_view(["GET"])
def game_list(request):
    games = _published().order_by("-created_at", "-id")
    return Response(GameSerializer(games, many=True).data)


@api_view(["GET"])
def game_detail(request, pk):
    game = _game_or_404(pk)
    if game is None:
        return Response(status=status.HTTP_404_NOT_FOUND)
    return Response(GameSerializer(game).data)


@api_view(["GET"])
def game_players(request, pk):
    game = _game_or_404(pk)
    if game is None:
        return Response(status=status.HTTP_404_NOT_FOUND)
    players = game.players.select_related("character").order_by("seat")
    return Response(
        PlayerSerializer(players, many=True, context={"request": request}).data
    )


@api_view(["GET"])
def game_beats(request, pk):
    game = _game_or_404(pk)
    if game is None:
        return Response(status=status.HTTP_404_NOT_FOUND)
    after = -1
    if "after" in request.query_params:
        after = _int_param(request, "after")
        if after is None:
            return Response(
                {"detail": "after must be an integer"},
                status=status.HTTP_400_BAD_REQUEST,
            )
    return Response([b for b in build_beats(game) if b["index"] > after])


@api_view(["GET"])
def game_notes(request, pk):
    game = _game_or_404(pk)
    if game is None:
        return Response(status=status.HTTP_404_NOT_FOUND)
    player_id = _int_param(request, "player")
    at = _int_param(request, "at")
    if player_id is None or at is None:
        return Response(
            {"detail": "player and at must be integers"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    player = game.players.filter(pk=player_id).first()
    if player is None:
        return Response(status=status.HTTP_404_NOT_FOUND)
    notes = notes_as_of(player, at)
    if notes is None:
        return Response({"player_id": player.id, "version": 0, "text": "", "at_seq": 0})
    return Response({
        "player_id": player.id,
        "version": notes.version,
        "text": notes.text,
        "at_seq": notes.at_seq,
    })
