from django.core.management.base import BaseCommand

from simulation.runner import run_tick
from world.models import AgentTick


class Command(BaseCommand):
    help = "Run one simulation tick, generating AgentTick records via LLM"

    def handle(self, *args, **options):
        tick = run_tick()
        count = AgentTick.objects.filter(tick=tick).count()
        self.stdout.write(
            self.style.SUCCESS(
                f"Tick {tick.id} complete — in_game_time={tick.in_game_time.isoformat()}, "
                f"{count} agent(s) processed"
            )
        )
