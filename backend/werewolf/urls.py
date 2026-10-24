from django.urls import path

from werewolf import views

urlpatterns = [
    path("games/", views.game_list),
    path("games/<int:pk>/", views.game_detail),
    path("games/<int:pk>/players/", views.game_players),
    path("games/<int:pk>/beats/", views.game_beats),
    path("games/<int:pk>/notes/", views.game_notes),
]
