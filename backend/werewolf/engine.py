"""The game engine: plays one night and day per ``run_day`` call.

Every phase handler derives its progress only from the GameEvents of the
current day, and only moves ``Game.phase`` on once its work is complete, so a
run that crashed part-way resumes without writing duplicate events.
"""

from collections import Counter
from typing import Protocol

from django.db import transaction

from werewolf.agents import LLMAgent, ScriptedAgent, WerewolfAgent
from werewolf.config import game_config
from werewolf.events import append_event
from werewolf.models import (
    ENGINE,
    LOVERS,
    PUBLIC,
    WOLF_CHAT,
    Game,
    GameEvent,
    Player,
    player_visibility,
)
from werewolf.moderator import (
    END_TOOL,
    PICK_TOOL,
    discussion_state,
    eligible_speakers,
    moderate,
)
from werewolf.prompts import Turn, build_prompt_for
from werewolf.rng import rng_for
from werewolf.tools import ValidationContext, match_name, tools_for
from werewolf.turns import BudgetExceeded, TurnResult, run_turn

Phase = Game.Phase


class AgentProvider(Protocol):
    def player_agent(self, player) -> WerewolfAgent: ...

    def moderator_agent(self) -> WerewolfAgent: ...


class LLMProvider:
    """One LLM agent for every player and the moderator."""

    def __init__(self, game: Game):
        self._agent = LLMAgent(timeout=game_config(game)["call_timeout_seconds"])

    def player_agent(self, player) -> WerewolfAgent:
        return self._agent

    def moderator_agent(self) -> WerewolfAgent:
        return self._agent


class ScriptedProvider:
    """A deterministic, LLM-free policy for ``run_day --scripted`` and tests.

    It is a stand-in for the LLM, not a prompt path, so it may read game state.
    Every message carries a unique token such as ``[Name d1 #3]``. Override the
    ``*_step`` hooks to control individual decisions.
    """

    def __init__(self, game: Game):
        self.game = game

    # -- agents ---------------------------------------------------------

    def player_agent(self, player) -> WerewolfAgent:
        return ScriptedAgent(lambda messages, tools: self._player_step(player, tools))

    def moderator_agent(self) -> WerewolfAgent:
        return ScriptedAgent(lambda messages, tools: self._moderator_step())

    # -- dispatch -------------------------------------------------------

    def _fresh_game(self) -> Game:
        return Game.objects.get(pk=self.game.pk)

    def _player_step(self, player, tools):
        from werewolf.models import AgentCall

        game = self._fresh_game()
        day = game.day_number
        n = AgentCall.objects.filter(game=game, player=player).count()
        by_name = {t["function"]["name"]: t["function"] for t in tools}
        if "vote" in by_name:
            return self.vote_step(player, day, n)
        if "protect" in by_name:
            return self.doctor_step(player, day, n)
        if "speak" in by_name:
            if "kill_target" in by_name["speak"]["parameters"]["properties"]:
                return self.wolf_step(player, day, n)
            if game.phase == Phase.NIGHT_LOVERS:
                return self.lovers_step(player, day, n)
            return self.discussion_step(player, day, n)
        kind = "seer_notes" if game.phase == Phase.NIGHT_SEER else "day_notes"
        return self.notes_step(player, day, n, kind)

    def _moderator_step(self):
        game = self._fresh_game()
        state = discussion_state(game)
        cfg = game_config(game)
        if state.messages_used >= cfg["discussion_min_messages"]:
            return [(END_TOOL, {"reason": "scripted: enough said"})]
        eligible = eligible_speakers(game, state)
        eligible.sort(key=lambda p: (state.per_player.get(p.id, 0), p.seat))
        return [(PICK_TOOL, {"name": eligible[0].name, "reason": "scripted: fewest"})]

    # -- policy hooks ---------------------------------------------------

    def wolf_step(self, player, day, n):
        game = self._fresh_game()
        targets = list(
            game.players.filter(alive=True).exclude(role="wolf").order_by("seat")
        )
        if rng_for(game, "scripted", "wolfmode", day).random() < 0.5:
            target = rng_for(game, "scripted", "kill", day).choice(targets)
        else:
            target = rng_for(game, "scripted", "kill", day, player.seat, n).choice(
                targets
            )
        return [
            (
                "speak",
                {
                    "message": f"[{player.wolf_label} d{day} #{n}] Let's pick one.",
                    "kill_target": target.name,
                },
            )
        ]

    def doctor_step(self, player, day, n):
        game = self._fresh_game()
        rng = rng_for(game, "scripted", "doctor", day)
        last = _last_protected_name(game, player)
        choices = [
            p
            for p in game.players.filter(alive=True).order_by("seat")
            if p.name != last
        ]
        if not choices or rng.random() < 0.2:
            return [("pass", {})]
        return [("protect", {"target": rng.choice(choices).name})]

    def lovers_step(self, player, day, n):
        game = self._fresh_game()
        rng = rng_for(game, "scripted", "lovers", player.seat, day, n)
        if rng.random() < 0.3:
            return [("pass", {})]
        return [
            (
                "speak",
                {"message": f"[{player.name} d{day} #{n} love] Thinking of you."},
            )
        ]

    def notes_step(self, player, day, n, kind):
        return [
            (
                "append_note",
                {"text": f"[{player.name} d{day} #{n} note] {kind} observation."},
            ),
            ("pass", {}),
        ]

    def discussion_step(self, player, day, n):
        game = self._fresh_game()
        rng = rng_for(game, "scripted", "speech", player.seat, day, n)
        if rng.random() < 0.15:
            return [("pass", {})]
        step = [
            (
                "speak",
                {"message": f"[{player.name} d{day} #{n}] Something feels off today."},
            )
        ]
        if rng.random() < 0.25:
            note = {"text": f"[{player.name} d{day} #{n} note] speech remark."}
            step.insert(0, ("append_note", note))
        return step

    def vote_step(self, player, day, n):
        game = self._fresh_game()
        rng = rng_for(game, "scripted", "vote", player.seat, day, n)
        others = list(
            game.players.filter(alive=True).exclude(pk=player.pk).order_by("seat")
        )
        if not others or rng.random() < 0.2:
            return [("vote", {"target": "none"})]
        return [("vote", {"target": rng.choice(others).name})]


# ---------------------------------------------------------------------------
# helpers


def _last_protected_name(game: Game, doctor) -> str | None:
    """Who the doctor protected on the previous night (None if nobody)."""
    previous = GameEvent.objects.filter(
        game=game, type="protect", actor=doctor, day=game.day_number - 1
    ).first()
    if previous is None:
        return None
    return Player.objects.get(pk=previous.payload["target_id"]).name


def validation_context(game: Game, player, kind: str) -> ValidationContext:
    players = list(game.players.select_related("character").order_by("seat"))
    living = [p for p in players if p.alive]
    return ValidationContext(
        turn_kind=kind,
        actor_role=player.role,
        actor_alive=player.alive,
        wolf_names=[p.name for p in players if p.role == Player.Role.WOLF],
        living_names=[p.name for p in living],
        living_non_wolf_names=[p.name for p in living if p.role != Player.Role.WOLF],
        speech_max_chars=game_config(game)["speech_max_chars"],
        actor_name=player.name,
        last_protected=(
            _last_protected_name(game, player) if kind == "doctor" else None
        ),
        actor_is_lover=player.lover_id is not None,
    )


def _today(game: Game, **filters):
    return GameEvent.objects.filter(game=game, day=game.day_number, **filters).order_by(
        "seq"
    )


def _living(game: Game) -> list[Player]:
    return list(game.players.filter(alive=True).select_related("character"))


def _resolve(name, candidates):
    return match_name(name, candidates, key=lambda p: p.name)


def _play(game, provider, player, kind, extra="") -> TurnResult:
    turn = Turn(
        phase=game.phase,
        day=game.day_number,
        kind=kind,
        allowed_tools=[t["function"]["name"] for t in tools_for(kind)],
        extra=extra,
    )
    return run_turn(
        game,
        player,
        provider.player_agent(player),
        turn,
        validation_context(game, player, kind),
        build_prompt_for(player, turn),
    )


def _write_pass(game, player) -> None:
    append_event(
        game,
        type="pass",
        visibility=ENGINE,
        actor=player,
        payload={"phase": game.phase},
    )


def _notes_turn(game, provider, player, kind) -> None:
    _play(game, provider, player, kind)
    append_event(
        game,
        type="notes_turn_done",
        visibility=ENGINE,
        actor=player,
        payload={"phase": game.phase},
    )


def _transition(game: Game, to: str, *, next_day: bool = False) -> None:
    with transaction.atomic():
        append_event(
            game,
            type="phase_change",
            visibility=ENGINE,
            payload={"from": game.phase, "to": to},
        )
        fields = {"phase": to}
        if next_day:
            fields["day_number"] = game.day_number + 1
        Game.objects.filter(pk=game.pk).update(**fields)
    game.refresh_from_db()


def _mark_dead(game: Game, player: Player, cause: str) -> None:
    player.alive = False
    player.save(update_fields=["alive"])
    reveal = game_config(game)["reveal_role_on_death"]
    append_event(
        game,
        type="death",
        visibility=PUBLIC,
        payload={
            "player_id": player.id,
            "cause": cause,
            "role": player.role if reveal else None,
            # Lovers are revealed along with roles.
            "lover_id": player.lover_id if reveal else None,
        },
    )


def _kill(game: Game, player_id: int, cause: str) -> None:
    """Kill a player; their living lover dies of a broken heart in the same
    transaction, so a resumed run never sees one death without the other."""
    with transaction.atomic():
        player = Player.objects.get(pk=player_id, game=game)
        _mark_dead(game, player, cause)
        if player.lover_id:
            lover = Player.objects.get(pk=player.lover_id)
            if lover.alive:
                _mark_dead(game, lover, "heartbreak")


def _end_game(game: Game, winner: str) -> None:
    with transaction.atomic():
        append_event(
            game, type="game_over", visibility=PUBLIC, payload={"winner": winner}
        )
        Game.objects.filter(pk=game.pk).update(
            status=Game.Status.FINISHED, phase=Phase.GAME_OVER, winner=winner
        )
    game.refresh_from_db()


def _check_win(game: Game) -> bool:
    living = _living(game)
    if len(living) == 2:
        a, b = living
        mixed = (a.role == Player.Role.WOLF) != (b.role == Player.Role.WOLF)
        if a.lover_id == b.id and b.lover_id == a.id and mixed:
            _end_game(game, Game.Winner.LOVERS)
            return True
    wolves = sum(1 for p in living if p.role == Player.Role.WOLF)
    others = len(living) - wolves
    if wolves == 0:
        _end_game(game, Game.Winner.TOWN)
    elif wolves >= others:
        _end_game(game, Game.Winner.WOLVES)
    else:
        return False
    return True


# ---------------------------------------------------------------------------
# phase handlers


def _agreed_target(wolves, messages) -> int | None:
    latest = {}
    for m in messages:
        if m.payload.get("kill_target_id") is not None:
            latest[m.actor_id] = m.payload["kill_target_id"]
    targets = {latest.get(w.id) for w in wolves}
    if len(targets) == 1 and None not in targets:
        return targets.pop()
    return None


def _engine_kill_target(game, messages) -> int:
    living = _living(game)
    living_non_wolves = sorted(
        (p for p in living if p.role != Player.Role.WOLF), key=lambda p: p.seat
    )
    named_ids = {m.payload.get("kill_target_id") for m in messages}
    named = [p for p in living_non_wolves if p.id in named_ids]
    rng = rng_for(game, "kill", game.day_number)
    return rng.choice(named or living_non_wolves).id


def _wolf_target_event(game, target_id, source) -> None:
    append_event(
        game,
        type="wolf_target",
        visibility=WOLF_CHAT,
        payload={"target_id": target_id, "source": source},
    )


def _night_wolf_chat(game, provider) -> None:
    cap = game_config(game)["wolf_chat_max_messages"]
    while not _today(game, type="wolf_target").exists():
        wolves = [p for p in _living(game) if p.role == Player.Role.WOLF]
        wolves.sort(key=lambda p: p.seat)
        phase_events = _today(game, phase=Phase.NIGHT_WOLF_CHAT)
        messages = list(phase_events.filter(type="wolf_message"))
        turns = phase_events.filter(type__in=["wolf_message", "pass"]).count()

        agreed = _agreed_target(wolves, messages) if wolves else None
        if agreed is not None:
            _wolf_target_event(game, agreed, "agreed")
        elif turns >= cap or not wolves:
            target_id = _engine_kill_target(game, messages)
            _wolf_target_event(game, target_id, "engine_random")
        else:
            _wolf_turn(
                game, provider, wolves[turns % len(wolves)], messages, turns, cap
            )
    _transition(game, Phase.NIGHT_DOCTOR)


def _wolf_turn(game, provider, wolf, messages, turns, cap) -> None:
    names = {p.id: p.name for p in game.players.all()}
    named = sorted({
        names[m.payload["kill_target_id"]]
        for m in messages
        if m.payload.get("kill_target_id")
    })
    extra = (
        f"Wolf chat messages used: {turns} of {cap}. "
        f"Kill targets named so far: {', '.join(named) or 'none'}."
    )
    result = _play(game, provider, wolf, "wolf_chat", extra)
    if result.action != "speak":
        _write_pass(game, wolf)
        return
    candidates = [p for p in _living(game) if p.role != Player.Role.WOLF]
    target = _resolve(result.args.get("kill_target"), candidates)
    append_event(
        game,
        type="wolf_message",
        visibility=WOLF_CHAT,
        actor=wolf,
        payload={
            "message": result.args["message"],
            "kill_target_id": target.id if target else None,
        },
    )


def _night_doctor(game, provider) -> None:
    doctor = next((p for p in _living(game) if p.role == Player.Role.DOCTOR), None)
    acted = _today(game, phase=Phase.NIGHT_DOCTOR, type__in=["protect", "pass"])
    if doctor and not acted.exists():
        result = _play(game, provider, doctor, "doctor")
        target = (
            _resolve(result.args.get("target"), _living(game))
            if result.action == "protect"
            else None
        )
        if target:
            append_event(
                game,
                type="protect",
                visibility=player_visibility(doctor.id),
                actor=doctor,
                payload={"target_id": target.id},
            )
        else:
            _write_pass(game, doctor)
    _transition(game, Phase.NIGHT_LOVERS)


def _night_lovers(game, provider) -> None:
    cap = game_config(game)["lovers_chat_max_messages"]
    lovers = sorted((p for p in _living(game) if p.lover_id), key=lambda p: p.seat)
    if len(lovers) == 2 and lovers[0].lover_id == lovers[1].id:
        while True:
            turns = list(
                _today(
                    game,
                    phase=Phase.NIGHT_LOVERS,
                    type__in=["lover_message", "pass"],
                )
            )
            if len(turns) >= cap or (
                len(turns) >= 2 and all(t.type == "pass" for t in turns[-2:])
            ):
                break
            lover = lovers[len(turns) % 2]
            result = _play(game, provider, lover, "lovers_chat")
            if result.action == "speak":
                append_event(
                    game,
                    type="lover_message",
                    visibility=LOVERS,
                    actor=lover,
                    payload={"message": result.args["message"]},
                )
            else:
                _write_pass(game, lover)
    _transition(game, Phase.NIGHT_SEER)


def _night_seer(game, provider) -> None:
    seer = next((p for p in _living(game) if p.role == Player.Role.SEER), None)
    if (
        seer
        and not _today(
            game, type="notes_turn_done", phase=Phase.NIGHT_SEER, actor=seer
        ).exists()
    ):
        _notes_turn(game, provider, seer, "seer_notes")
    _transition(game, Phase.MORNING)


def _morning(game, provider) -> None:
    target = _today(game, type="wolf_target").first()
    protect = _today(game, type="protect").first()
    saved = bool(
        target
        and protect
        and protect.payload["target_id"] == target.payload["target_id"]
    )
    if target and protect and not _today(game, type="save_result").exists():
        append_event(
            game,
            type="save_result",
            visibility=protect.visibility,
            payload={"saved": saved},
        )
    if target and saved:
        if not _today(game, type="peaceful_night").exists():
            append_event(game, type="peaceful_night", visibility=PUBLIC)
    elif (
        target and not _today(game, type="death", payload__cause="night_kill").exists()
    ):
        _kill(game, target.payload["target_id"], "night_kill")
    if _check_win(game):
        return
    _transition(game, Phase.DISCUSSION)


def _discussion(game, provider) -> None:
    while True:
        state = discussion_state(game)
        if state.ended:
            break
        last = _today(
            game,
            phase=Phase.DISCUSSION,
            type__in=["speech", "pass", "moderator_pick"],
        ).last()
        if last and last.type == "moderator_pick":
            payload = last.payload  # a crashed run already asked the moderator
        else:
            payload = moderate(game, provider.moderator_agent(), state)
        if payload["end"]:
            break
        speaker = Player.objects.select_related("character").get(pk=payload["pick_id"])
        result = _play(
            game,
            provider,
            speaker,
            "discussion",
            "The moderator has invited you to speak.",
        )
        if result.action == "speak":
            append_event(
                game,
                type="speech",
                visibility=PUBLIC,
                actor=speaker,
                payload={"message": result.args["message"]},
            )
        else:
            _write_pass(game, speaker)
    _transition(game, Phase.VOTE)


def _tally(game, living, casts):
    votes = [
        {"voter_id": p.id, "target_id": casts[p.id]} for p in living if p.id in casts
    ]
    counts = Counter(
        "none" if v["target_id"] is None else str(v["target_id"]) for v in votes
    )
    none_votes = counts.get("none", 0)
    player_votes = {k: n for k, n in counts.items() if k != "none"}
    eliminated = None
    if none_votes <= len(living) / 2 and player_votes:
        top = max(player_votes.values())
        leaders = [k for k, n in player_votes.items() if n == top]
        if len(leaders) == 1:
            eliminated = int(leaders[0])
    return votes, dict(counts), eliminated


def _vote(game, provider) -> None:
    if not _today(game, type="vote_result").exists():
        living = sorted(_living(game), key=lambda p: p.seat)
        casts = {
            e.actor_id: e.payload["target_id"] for e in _today(game, type="vote_cast")
        }
        for voter in living:
            if voter.id in casts:
                continue
            result = _play(game, provider, voter, "vote")
            others = [p for p in living if p.id != voter.id]
            target = _resolve(result.args.get("target"), others)
            casts[voter.id] = target.id if target else None
            append_event(
                game,
                type="vote_cast",
                visibility=ENGINE,
                actor=voter,
                payload={"target_id": casts[voter.id]},
            )
        votes, tally, eliminated = _tally(game, living, casts)
        public = game_config(game)["votes_public"]
        append_event(
            game,
            type="vote_result",
            visibility=PUBLIC,
            payload={
                "votes": votes if public else [],
                "tally": tally,
                "eliminated_id": eliminated,
            },
        )
    _transition(game, Phase.ELIMINATION)


def _elimination(game, provider) -> None:
    result = _today(game, type="vote_result").first()
    eliminated = result.payload["eliminated_id"] if result else None
    if eliminated and not _today(game, type="death", payload__cause="vote").exists():
        _kill(game, eliminated, "vote")
    if _check_win(game):
        return
    _transition(game, Phase.DAY_NOTES)


def _day_notes(game, provider) -> None:
    for player in sorted(_living(game), key=lambda p: p.seat):
        done = _today(
            game, type="notes_turn_done", phase=Phase.DAY_NOTES, actor=player
        ).exists()
        if not done:
            _notes_turn(game, provider, player, "day_notes")
    if game.day_number >= game_config(game)["max_days"]:
        _end_game(game, Game.Winner.DRAW)
    else:
        _transition(game, Phase.DAY_END)


def _day_end(game, provider) -> None:
    _transition(game, Phase.NIGHT_WOLF_CHAT, next_day=True)


HANDLERS = {
    Phase.NIGHT_WOLF_CHAT: _night_wolf_chat,
    Phase.NIGHT_DOCTOR: _night_doctor,
    Phase.NIGHT_LOVERS: _night_lovers,
    Phase.NIGHT_SEER: _night_seer,
    Phase.MORNING: _morning,
    Phase.DISCUSSION: _discussion,
    Phase.VOTE: _vote,
    Phase.ELIMINATION: _elimination,
    Phase.DAY_NOTES: _day_notes,
    Phase.DAY_END: _day_end,
}


def run_day(game: Game, provider: AgentProvider) -> None:
    """Play from the current phase to the end of the day (or game over)."""
    game.refresh_from_db()
    try:
        while game.status == Game.Status.ACTIVE:
            phase = game.phase
            if phase not in HANDLERS:
                raise ValueError(f"Cannot run a day from phase {phase!r}")
            HANDLERS[phase](game, provider)
            if phase == Phase.DAY_NOTES:
                break
    except BudgetExceeded:
        game.refresh_from_db()
