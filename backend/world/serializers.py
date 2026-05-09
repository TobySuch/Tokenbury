from rest_framework import serializers
from world.models import Location


class LocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Location
        fields = [
            "id",
            "slug",
            "name",
            "description",
            "bbox_x1",
            "bbox_y1",
            "bbox_x2",
            "bbox_y2",
        ]
