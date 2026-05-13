from django.core.management.base import BaseCommand

from simulation.runner import SimulationAlreadyUpToDate, run_tick
from world.models import AgentTick


class Command(BaseCommand):
    help = "Run one simulation tick, generating AgentTick records via LLM"

    def add_arguments(self, parser):
        parser.add_argument(
            "--catchup",
            action="store_true",
            help="Set in_game_time to current real-world time (rounded to the nearest interval) instead of advancing sequentially. Use to recover after downtime.",
        )

    def handle(self, *args, **options):
        catchup = options["catchup"]
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
