"""FAUX serveur, uniquement pour tester le client tant que serveur/serveur.py (Youssef) n'existe pas.

    python -m outils.faux_serveur

Ville : le vrai réseau de rues de Colmar, lu dans assets/colmar.json (fait par
outils/extraire_osm.py). Le trajet est le plus court en distance (Dijkstra simple),
sans trafic ni sens uniques : ce n'est pas le vrai calcul de Youssef. Plusieurs clients possibles.
"""

import json
import os
import select
import socket
from pathlib import Path

from sae.protocole import PORT_TCP, Deframeur, encoder

VITESSE = 13.9       # m/s (50 km/h)

VILLE = json.loads((Path(__file__).parent.parent / "assets" / "colmar.json").read_text(encoding="utf-8"))
NOEUDS = VILLE["noeuds"]
ROUTES = VILLE["routes"]
LIEUX = VILLE["lieux"]
RUES = VILLE["rues"]

VOISINS = {n: [] for n in NOEUDS}          # noeud -> [(voisin, longueur), ...]
for a, b, longueur in ROUTES:
    VOISINS[a].append((b, longueur))
    VOISINS[b].append((a, longueur))


def chemin_le_plus_court(depart, arrivee):
    """Dijkstra : on agrandit petit à petit la zone des noeuds dont on connaît la distance."""
    distance = {depart: 0}
    precedent = {depart: None}
    a_traiter = {depart}
    while a_traiter:
        noeud = min(a_traiter, key=lambda n: distance[n])   # le plus proche pas encore traité
        a_traiter.remove(noeud)
        if noeud == arrivee:
            break
        for voisin, longueur in VOISINS[noeud]:
            nouvelle = distance[noeud] + longueur
            if voisin not in distance or nouvelle < distance[voisin]:
                distance[voisin] = nouvelle
                precedent[voisin] = noeud
                a_traiter.add(voisin)
    if arrivee not in precedent:
        return None, 0
    chemin = [arrivee]
    while chemin[-1] != depart:
        chemin.append(precedent[chemin[-1]])
    return chemin[::-1], distance[arrivee]


def repondre(message):
    if message["type"] == "GET_CITY":
        return {"type": "CITY", "noeuds": NOEUDS, "routes": ROUTES, "lieux": LIEUX, "rues": RUES}
    if message["type"] == "COMPUTE_ROUTE":
        for nom in (message["depart"], message["arrivee"]):
            if nom not in NOEUDS:
                return {"type": "ERROR", "raison": f"noeud inconnu : {nom}"}
        chemin, distance = chemin_le_plus_court(message["depart"], message["arrivee"])
        if chemin is None:
            return {"type": "ERROR", "raison": "aucun chemin entre ces deux points"}
        return {"type": "ROUTE", "chemin": chemin, "distance": round(distance, 1),
                "temps": round(distance / VITESSE, 1)}
    return {"type": "ERROR", "raison": f"type inconnu : {message['type']}"}


def main():
    ecoute = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    if os.name != "nt":
        # Sous Linux : relancer tout de suite sans "Address already in use".
        # Pas sous Windows : là-bas, ça permettrait à DEUX serveurs d'écouter sur le même port.
        ecoute.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    ecoute.bind(("0.0.0.0", PORT_TCP))
    ecoute.listen()
    print(f"Faux serveur en écoute sur le port {PORT_TCP} (Ctrl+C pour arrêter)")
    clients = {}                      # socket -> Deframeur
    while True:
        lisibles, _, _ = select.select([ecoute, *clients], [], [], 0.5)
        for s in lisibles:
            if s is ecoute:
                conn, adresse = ecoute.accept()
                clients[conn] = Deframeur()
                print("connexion de", adresse)
                continue
            try:
                octets = s.recv(4096)
                if not octets:
                    raise ConnectionError("fermée par le client")
                for message in clients[s].alimenter(octets):
                    print("reçu  :", message)
                    reponse = repondre(message)
                    print("envoi :", reponse["type"])
                    s.sendall(encoder(reponse))
            except (OSError, ValueError) as e:
                print("déconnexion :", e)
                del clients[s]
                s.close()


if __name__ == "__main__":
    main()
