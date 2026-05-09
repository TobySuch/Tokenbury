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
