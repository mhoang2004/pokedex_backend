import json
import random
import requests

from django.shortcuts import render
from django.http import JsonResponse
from django.contrib.auth.models import User
from django.views.decorators.csrf import csrf_exempt

from rest_framework import generics
from rest_framework.permissions import IsAuthenticated, AllowAny

from .constants import BASE_URL
from .serializers import UserSerializer


class CreateUserView(generics.CreateAPIView):
    queryset = User.objects. all()
    serializer_class = UserSerializer
    permission_classes = [AllowAny]


def pokemon_card(url):
    if "pokemon-species" in url:
        url = url.replace("pokemon-species", "pokemon")

    data = requests.get(url).json()

    return {
        "name": data.get("name"),
        "image": data.get("sprites")
    }


@csrf_exempt
def get_pokemons(request, page):
    quantity = 36
    offset = quantity * page

    response = requests.get(
        f'{BASE_URL}/pokemon?limit={quantity}&offset={offset}')

    pokemons = response.json().get('results', [])

    results = []
    for pokemon in pokemons:
        data = pokemon_card(pokemon["url"])
        results.append(data)

    return JsonResponse({"results": results})


@csrf_exempt
def filter_pokemon(request):
    if request.method == 'POST':
        # get data from post
        data = json.loads(request.body)
        name = data.get('name', '')

        if not name:
            return JsonResponse({'filtered_pokemon': []}, safe=False)

        # make request to Poke API
        response = requests.get(
            f'{BASE_URL}/pokemon?limit=10000')

        # filter pokemon
        all_pokemon = response.json().get('results', [])
        filtered_pokemon = [
            pokemon for pokemon in all_pokemon if name in pokemon['name']]

        return JsonResponse({'filtered_pokemon': filtered_pokemon}, safe=False)
    else:
        return JsonResponse({'error': 'Invalid request method'}, status=405)


@csrf_exempt
def get_pokemon(request, name):
    url = f"{BASE_URL}/pokemon/{name}"
    response = requests.get(url)

    pokemon = response.json()

    result = {
        "id": pokemon.get("id"),
        "japanese_name": "ブランク",
        "overview": "Nothing.",
        "name": pokemon.get("name").replace("-", " "),
        "height": pokemon.get("height"),
        "weight": pokemon.get("weight"),
        "sprites": pokemon.get("sprites"),
        "types": pokemon.get("types"),
        "category": "Unknown",
        "evolution_chain": {},
        "stat": {},
        "weakness": [],
        "abilities": [],
        "genders": [],
        "varieties": [],
    }

    # abilities
    for ability_obj in pokemon["abilities"]:
        ability_url = ability_obj["ability"]["url"]
        ability = requests.get(ability_url).json()
        ability_flavor_text = ability["flavor_text_entries"][0]["flavor_text"]

        for flavor_text in ability["flavor_text_entries"]:
            if flavor_text["language"]["name"] == "en":
                ability_flavor_text = flavor_text["flavor_text"]
                break

        result["abilities"].append({
            "name": ability["name"].replace("-", " "),
            "text": ability_flavor_text,
            "is_hidden": ability_obj["is_hidden"]
        })

    species_response = requests.get(pokemon['species']['url'])
    species_data = species_response.json()

    female_data = requests.get(f"{BASE_URL}/gender/1").json()
    female_pokemons = [f["pokemon_species"]["name"]
                       for f in female_data["pokemon_species_details"]]
    male_data = requests.get(f"{BASE_URL}/gender/2").json()
    male_pokemons = [m["pokemon_species"]["name"]
                     for m in male_data["pokemon_species_details"]]

    # varieties
    varieties = species_data.get("varieties", [])
    for variety in varieties:
        variety_pokemon = pokemon_card(variety["pokemon"]["url"])
        variety_pokemon["is_default"] = variety["is_default"]
        result["varieties"].append(variety_pokemon)

    # weakness
    weaknesses = []
    explored_weaknesses = []

    for type_obj in pokemon.get("types"):
        type = requests.get(type_obj["type"]["url"]).json()

        for weakness_type in type["damage_relations"]["double_damage_from"]:
            weaknesses.append(weakness_type["name"])

    for type_name in weaknesses:
        if type_name not in explored_weaknesses:
            result["weakness"].append({"name": type_name, "detail": weaknesses.count(
                type_name) * 2})

        explored_weaknesses.append(type_name)

    # evolution chain
    evol_url = species_data["evolution_chain"]["url"]
    evol_data = requests.get(evol_url).json()
    evol_chain = evol_data["chain"]

    def helper_evol(evol):
        poke_info = pokemon_card(evol["species"]["url"])
        if evol["evolves_to"]:
            return {
                "species": poke_info,
                "evolves_to": [helper_evol(e) for e in evol["evolves_to"]]
            }
        else:
            return {
                "species": poke_info,
                "evolves_to": []
            }

    result["evolution_chain"] = helper_evol(evol_chain)

    # overview
    for overview in species_data["flavor_text_entries"]:
        if overview["language"]["name"] == "en" and overview["version"]["name"] == "x":
            result["overview"] = overview["flavor_text"]
            break

    # gender
    if pokemon["name"] in male_pokemons:
        result["genders"].append(2)
    if pokemon["name"] in female_pokemons:
        result["genders"].append(1)

    # category
    for genus in species_data['genera']:
        if genus['language']['name'] == 'en':
            result["category"] = genus['genus'].replace(" Pokémon", "")
            break

    # japanese name
    for name in species_data['names']:
        if name['language']['name'] == 'ja-Hrkt':
            result["japanese_name"] = name['name']
            break

    # stats
    def max_stat(base_stat, level=100, iv=31, ev=255, nature=1.0):
        max_stat = (((2 * base_stat + iv + (ev // 4))
                    * level // 100) + 5) * nature
        return int(max_stat)

    for stat in pokemon.get("stats", []):
        base = stat['base_stat']

        key = stat['stat']['name']
        value = int((base / max_stat(base)) * 100)

        result["stat"][key] = value

    return JsonResponse(result)
