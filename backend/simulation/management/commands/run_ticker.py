import fcntl

from django.core.management.base import BaseCommand

from simulation.runner import SimulationAlreadyUpToDate, run_tick
from world.models import AgentTick

LOCK_FILE = "/tmp/tokenbury-ticker.lock"


class Command(BaseCommand):
    help = "Run one simulation tick, generating AgentTick records via LLM"

    def add_arguments(self, parser):
        parser.add_argument(
            "--catchup",
            action="store_true",
            help="Set in_game_time to current real-world time (rounded to the nearest interval) instead of advancing sequentially. Use to recover after downtime.",
        )

    def handle(self, *args, **options):
        lock_fd = open(LOCK_FILE, "w")
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.stdout.write(
                self.style.WARNING(
                    "Another ticker process is already running — skipping."
                )
            )
            lock_fd.close()
            return
        try:
            self._run(options["catchup"])
        finally:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
            lock_fd.close()

    def _run(self, catchup: bool) -> None:
        if catchup:
            self.stdout.write("Catchup mode: jumping to current real-world time.")
        try:
            tick = run_tick(catchup=catchup)
        except SimulationAlreadyUpToDate as e:
            self.stdout.write(
                self.style.WARNING(
                    f"Already up to date — most recent tick is {e.tick.in_game_time.isoformat()}, no new tick created."
                )
            )
            return
        count = AgentTick.objects.filter(tick=tick).count()
        self.stdout.write(
            self.style.SUCCESS(
                f"Tick {tick.id} complete — in_game_time={tick.in_game_time.isoformat()}, "
                f"{count} agent(s) processed"
            )
        )
