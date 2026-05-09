from rest_framework.decorators import api_view
from rest_framework.response import Response

from world.models import Location
from world.serializers import LocationSerializer


@api_view(["GET"])
def health(request):
    return Response({"status": "ok", "message": "Tokenbury is alive 🌊"})


@api_view(["GET"])
def locations(request):
    return Response(LocationSerializer(Location.objects.all(), many=True).data)
