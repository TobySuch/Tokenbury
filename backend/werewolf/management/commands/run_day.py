import fcntl

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Sum
from django.utils import timezone

from werewolf.engine import LLMProvider, ScriptedProvider, run_day
from werewolf.models import AgentCall, Game, GameEvent

LOCK_FILE = "/tmp/tokenbury-werewolf.lock"


def now_local():
    return timezone.localtime()


class Command(BaseCommand):
    help = "Play one night and day of a werewolf game."

    def add_arguments(self, parser):
        parser.add_argument("--game", type=int, default=None, help="Game id")
        parser.add_argument(
            "--scripted",
            action="store_true",
            help="Use the deterministic no-LLM agents.",
        )
        parser.add_argument(
            "--if-due",
            action="store_true",
            help="Only run after WEREWOLF_RUN_HOUR and once per local day.",
        )
        parser.add_argument(
            "--until-over",
            action="store_true",
            help="Keep playing days until the game ends.",
        )

    def handle(self, *args, **options):
        lock_fd = open(LOCK_FILE, "w")  # noqa: SIM115 - held open for the process lifetime
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.stdout.write(
                self.style.WARNING("Another werewolf run is in progress - skipping.")
            )
            lock_fd.close()
            return
        try:
            self._run(options)
        finally:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
            lock_fd.close()

    def _find_game(self, game_id):
        if game_id is not None:
            try:
                return Game.objects.get(pk=game_id)
            except Game.DoesNotExist:
                raise CommandError(f"Game {game_id} does not exist") from None
        return Game.objects.filter(status=Game.Status.ACTIVE).order_by("-id").first()

    def _day_completed_today(self, game) -> bool:
        today = now_local().date()
        events = GameEvent.objects.filter(game=game).filter(
            type=GameEvent.Type.GAME_OVER
        ) | GameEvent.objects.filter(
            game=game,
            type=GameEvent.Type.PHASE_CHANGE,
            payload__to=Game.Phase.NIGHT_WOLF_CHAT,
        )
        latest = events.order_by("-seq").first()
        return (
            latest is not None and timezone.localtime(latest.created_at).date() == today
        )

    def _run(self, options):
        game = self._find_game(options["game"])
        if game is None:
            self.stdout.write("No active game to run.")
            return
        if game.status != Game.Status.ACTIVE:
            self.stdout.write(f"Game {game.pk} is {game.status}; nothing to run.")
            return
        if options["if_due"]:
            if now_local().hour < settings.WEREWOLF_RUN_HOUR:
                self.stdout.write("Not due yet: before the run hour.")
                return
            if self._day_completed_today(game):
                self.stdout.write("Not due: a day has already been completed today.")
                return

        provider = ScriptedProvider(game) if options["scripted"] else LLMProvider(game)
        while True:
            before = (game.day_number, game.phase)
            run_day(game, provider)
            game.refresh_from_db()
            if not options["until_over"] or game.status != Game.Status.ACTIVE:
                break
            if (game.day_number, game.phase) == before:
                break
        self._summary(game)

    def _summary(self, game):
        deaths = GameEvent.objects.filter(game=game, type=GameEvent.Type.DEATH)
        names = {p.pk: p.name for p in game.players.select_related("character")}
        death_text = (
            ", ".join(
                f"{names[e.payload['player_id']]} (day {e.day}, {e.payload['cause']})"
                for e in deaths
            )
            or "none"
        )
        calls = AgentCall.objects.filter(game=game)
        totals = calls.aggregate(tin=Sum("tokens_in"), tout=Sum("tokens_out"))
        self.stdout.write(
            f"Game {game.pk}: day {game.day_number}, phase {game.phase}, "
            f"status {game.status}\n"
            f"Deaths: {death_text}\n"
            f"Winner: {game.winner or 'none yet'}\n"
            f"Agent calls: {calls.count()} "
            f"(tokens in {totals['tin'] or 0}, out {totals['tout'] or 0})"
        )
