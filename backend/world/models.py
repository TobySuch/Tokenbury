from django.db import models


class Instance(models.Model):
    name = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    map_image = models.ImageField(upload_to="maps/")
    created_at = models.DateTimeField(auto_now_add=True)
    active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class Banner(models.Model):
    text = models.TextField()
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.text[:50]


class Agent(models.Model):
    instance = models.ForeignKey(
        Instance,
        on_delete=models.CASCADE,
        related_name="agents",
    )
    name = models.CharField(max_length=200)
    bio = models.TextField()
    sprite = models.ImageField(upload_to="sprites/")
    active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class Location(models.Model):
    instance = models.ForeignKey(
        Instance,
        on_delete=models.CASCADE,
        related_name="locations",
    )
    slug = models.SlugField()
    name = models.CharField(max_length=200)
    description = models.TextField()
    bbox_x1 = models.FloatField()
    bbox_y1 = models.FloatField()
    bbox_x2 = models.FloatField()
    bbox_y2 = models.FloatField()

    class Meta:
        unique_together = [("instance", "slug")]

    def __str__(self):
        return self.name


class Tick(models.Model):
    instance = models.ForeignKey(
        Instance,
        on_delete=models.CASCADE,
        related_name="ticks",
    )
    in_game_time = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    active = models.BooleanField(default=False)

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
    raw_prompts = models.JSONField(default=dict, blank=True)
    raw_responses = models.JSONField(default=dict, blank=True)

    class Meta:
        unique_together = [("agent", "tick")]
        ordering = ["agent__name"]

    def __str__(self):
        return f"{self.agent.name} @ tick {self.tick_id}"


class DailyPlan(models.Model):
    agent = models.ForeignKey(
        Agent, on_delete=models.CASCADE, related_name="daily_plans"
    )
    date = models.DateField()
    plan = models.JSONField()
    generated_at_tick = models.ForeignKey(
        Tick, on_delete=models.SET_NULL, null=True, related_name="daily_plans"
    )

    class Meta:
        unique_together = [("agent", "date")]

    def __str__(self):
        return f"{self.agent.name}'s plan for {self.date}"
