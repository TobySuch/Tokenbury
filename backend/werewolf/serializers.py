from rest_framework import serializers

from werewolf.models import Game, Player


class GameSerializer(serializers.ModelSerializer):
    class Meta:
        model = Game
        fields = ["id", "status", "phase", "day_number", "winner", "created_at"]


class PlayerSerializer(serializers.ModelSerializer):
    name = serializers.CharField(read_only=True)
    avatar_url = serializers.SerializerMethodField()
    lover_id = serializers.IntegerField(read_only=True, allow_null=True)

    def get_avatar_url(self, obj):
        avatar = obj.character.avatar
        if not avatar:
            return None
        request = self.context.get("request")
        return request.build_absolute_uri(avatar.url) if request else avatar.url

    class Meta:
        model = Player
        fields = [
            "id",
            "name",
            "seat",
            "avatar_url",
            "role",
            "wolf_label",
            "alive",
            "lover_id",
        ]
