from django.core.management.base import BaseCommand, CommandError

from werewolf.setup import create_game


class Command(BaseCommand):
    help = "Create a new werewolf game."

    def add_arguments(self, parser):
        parser.add_argument("--seed", type=int, default=None)
        parser.add_argument(
            "--config",
            nargs="*",
            default=[],
            metavar="KEY=VALUE",
            help="Config overrides",
        )

    def handle(self, *args, **options):
        overrides = {}
        for item in options["config"]:
            key, sep, value = item.partition("=")
            if not sep:
                raise CommandError(f"Config must be key=value, got {item!r}")
            overrides[key] = value
        try:
            game = create_game(seed=options["seed"], config=overrides)
        except ValueError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(f"Created game {game.pk} (seed {game.seed}).")
