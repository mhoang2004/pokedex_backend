from django.urls import path, include
from . import views


urlpatterns = [
    path("get_pokemons/<int:page>", views.get_pokemons, name="get-pokemons"),
    path("get_pokemon/<str:name>",
         views.get_pokemon, name="get-pokemon"),

    path("filter_pokemon/", views.filter_pokemon, name="filter-pokemon"),
]
