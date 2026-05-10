from django.db import models


class Agent(models.Model):
    name = models.CharField(max_length=200)
    bio = models.TextField()
    sprite = models.ImageField(upload_to="sprites/")
    active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class Location(models.Model):
    slug = models.SlugField(unique=True)
    name = models.CharField(max_length=200)
    description = models.TextField()
    bbox_x1 = models.FloatField()
    bbox_y1 = models.FloatField()
    bbox_x2 = models.FloatField()
    bbox_y2 = models.FloatField()

    def __str__(self):
        return self.name


class Tick(models.Model):
    in_game_time = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-in_game_time"]

    def __str__(self):
        return f"Tick {self.pk} — {self.in_game_time}"


class AgentTick(models.Model):
    agent = models.ForeignKey(Agent, on_delete=models.CASCADE, related_name="ticks")
    tick = models.ForeignKey(
        Tick, on_delete=models.CASCADE, related_name="agent_states"
    )
    location = models.ForeignKey(
        Location,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="agent_ticks",
    )
    activity = models.TextField()
    inner_thought = models.TextField()
    mood = models.CharField(max_length=100, blank=True)
    raw_prompt = models.TextField(blank=True)
    raw_response = models.TextField(blank=True)

    class Meta:
        unique_together = [("agent", "tick")]
        ordering = ["agent__name"]

    def __str__(self):
        return f"{self.agent.name} @ tick {self.tick_id}"
