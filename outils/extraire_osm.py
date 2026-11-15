"""Convertit les rues de Colmar téléchargées sur Overpass en ville prête pour le projet.

    python -m outils.extraire_osm

Entrée  : assets/colmar_osm.json (requête Overpass, format JSON)
Sortie  : assets/colmar.json (noeuds en mètres, routes avec longueur, sens uniques, feux, lieux, rues)
On ne le lance qu'une fois (ou quand on change de zone) : ensuite tout le monde lit colmar.json.
"""

import json
import math
from pathlib import Path

DOSSIER = Path(__file__).parent.parent / "assets"

# Bords de assets/colmar.png (les mêmes que dans la requête Overpass)
SUD, OUEST, NORD, EST = 48.06905, 7.33209, 48.08209, 7.36676
LARGEUR = 2579                     # mètres couverts par l'image, d'ouest en est


def mercator(lat):
    """Donne la position verticale d'une latitude sur une carte Mercator.

    Args:
        lat (float): latitude en degrés.

    Returns:
        float: position sans unité (à multiplier par ECHELLE pour avoir des mètres).
    """
    return math.log(math.tan(math.pi / 4 + math.radians(lat) / 2))


ECHELLE = LARGEUR / math.radians(EST - OUEST)    # mètres par unité de carte


def en_metres(lat, lon):
    """Convertit une position GPS en mètres depuis le coin haut-gauche de l'image.

    Args:
        lat (float): latitude en degrés.
        lon (float): longitude en degrés.

    Returns:
        tuple[float, float]: (x, y) en mètres, arrondis au décimètre.
    """
    x = math.radians(lon - OUEST) * ECHELLE
    y = (mercator(NORD) - mercator(lat)) * ECHELLE
    return round(x, 1), round(y, 1)


HAUTEUR = en_metres(SUD, OUEST)[1]   # mètres couverts par l'image, du nord au sud

# Lieux proposés comme départ / arrivée : (lat, lon) relevés dans OpenStreetMap.
# Chacun sera rattaché au point de rue le plus proche.
LIEUX = {
    "Hôpital Pasteur": (48.07480, 7.33840),
    "Gare de Colmar": (48.07265, 7.34652),
    "Gare Saint-Joseph": (48.08169, 7.34530),
    "Commissariat de police": (48.08187, 7.36310),
    "Musée Unterlinden": (48.07986, 7.35556),
    "Théâtre municipal": (48.07982, 7.35478),
    "Champ de Mars": (48.07616, 7.35375),
    "Petite Venise": (48.07399, 7.35730),
    "Mairie annexe": (48.07375, 7.33257),
}


def dans_image(x, y):
    """Dit si un point est dans le fond de carte assets/colmar.png.

    Args:
        x (float): abscisse en mètres.
        y (float): ordonnée en mètres.

    Returns:
        bool: True si le point est dans l'image.
    """
    return 0 <= x <= LARGEUR and 0 <= y <= HAUTEUR


def plus_proche(noeuds, x, y):
    """Trouve le noeud le plus proche d'un point.

    Args:
        noeuds (dict[str, tuple]): noeud -> (x, y) en mètres.
        x (float): abscisse en mètres.
        y (float): ordonnée en mètres.

    Returns:
        str: l'identifiant du noeud.
    """
    return min(noeuds, key=lambda n: math.hypot(noeuds[n][0] - x, noeuds[n][1] - y))


def extraire():
    """Lit assets/colmar_osm.json et construit la ville du projet.

    Returns:
        dict: "noeuds", "routes" (avec longueur), "sens_uniques", "feux", "lieux" et "rues".
    """
    elements = json.loads((DOSSIER / "colmar_osm.json").read_text(encoding="utf-8"))["elements"]

    positions = {}
    feux = set()
    for e in elements:
        if e["type"] == "node":
            positions[str(e["id"])] = en_metres(e["lat"], e["lon"])
            if e.get("tags", {}).get("highway") == "traffic_signals":
                feux.add(str(e["id"]))

    routes = []
    sens_uniques = []
    points_des_rues = {}                        # nom de la rue -> points gardés de cette rue
    for e in elements:
        if e["type"] != "way":
            continue
        tags = e.get("tags", {})
        points = [str(n) for n in e["nodes"]]
        if tags.get("oneway") == "-1":         # sens unique "à l'envers" : on retourne la rue
            points.reverse()
        sens_unique = tags.get("oneway") in ("yes", "-1") or tags.get("junction") == "roundabout"

        for a, b in zip(points, points[1:]):    # paires de points qui se suivent
            (xa, ya), (xb, yb) = positions[a], positions[b]
            if not (dans_image(xa, ya) and dans_image(xb, yb)):
                continue                        # ce morceau de rue sort de l'image
            routes.append([a, b, round(math.hypot(xb - xa, yb - ya), 1)])
            if sens_unique:
                sens_uniques.append([a, b])     # on ne peut aller que de a vers b
            if "name" in tags:                  # une rue peut être coupée en plusieurs "way"
                points_des_rues.setdefault(tags["name"], set()).update((a, b))

    # On ne garde que les points qui servent à au moins une route
    utilises = {a for a, _, _ in routes} | {b for _, b, _ in routes}
    noeuds = {n: positions[n] for n in utilises}
    lieux = {nom: plus_proche(noeuds, *en_metres(lat, lon)) for nom, (lat, lon) in LIEUX.items()}

    # Chaque rue est représentée par son point le plus proche du centre de la rue
    rues = {}
    for nom, points in sorted(points_des_rues.items()):
        centre_x = sum(noeuds[p][0] for p in points) / len(points)
        centre_y = sum(noeuds[p][1] for p in points) / len(points)
        rues[nom] = plus_proche({p: noeuds[p] for p in points}, centre_x, centre_y)

    return {"noeuds": noeuds, "routes": routes, "sens_uniques": sens_uniques,
            "feux": sorted(feux & utilises), "lieux": lieux, "rues": rues}


if __name__ == "__main__":
    ville = extraire()
    sortie = DOSSIER / "colmar.json"
    sortie.write_text(json.dumps(ville, ensure_ascii=False), encoding="utf-8")
    print(f"{sortie} écrit : {len(ville['noeuds'])} noeuds, {len(ville['routes'])} routes, "
          f"{len(ville['feux'])} feux, {len(ville['lieux'])} lieux, {len(ville['rues'])} rues")
