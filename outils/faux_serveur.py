"""FAUX serveur, uniquement pour tester le client tant que serveur/serveur.py (Youssef) n'existe pas.

    python -m outils.faux_serveur

Ville : le vrai réseau de rues de Colmar, lu dans assets/colmar.json (fait par
outils/extraire_osm.py). Plusieurs clients possibles.

En TCP (port 5050) : GET_CITY -> CITY (avec "feux"), GET_TRAFFIC -> TRAFFIC,
COMPUTE_ROUTE -> ROUTES (les 3 trajets), GET_HISTORY -> HISTORY.
En UDP (port 5051), il joue les carrefours : PRIORITY_REQUEST -> PRIORITY_GRANT (toujours accordé).
Sauf GET_CITY et COMPUTE_ROUTE, ce sont NOS PROPOSITIONS de messages, pas encore validées
par Youssef. Les calculs sont volontairement grossiers (trafic inventé, sens uniques ignorés) :
ce n'est pas le vrai calcul de Youssef.
"""

import json
import math
import os
import select
import socket
import sqlite3
from datetime import datetime
from pathlib import Path

from sae.protocole import PORT_TCP, PORT_UDP, Deframeur, decoder, encoder

VITESSE = 13.9       # m/s (50 km/h)
ATTENTE_FEU = 15     # pénalité moyenne d'un feu, pour que Dijkstra "trafic" évite les feux
CYCLE_FEU = 60       # chaque feu : 30 s vert puis 30 s rouge (même règle que client/carte.py)
DUREE_VERT = 30

VILLE = json.loads((Path(__file__).parent.parent / "assets" / "colmar.json").read_text(encoding="utf-8"))
NOEUDS = VILLE["noeuds"]
ROUTES = VILLE["routes"]
LIEUX = VILLE["lieux"]
RUES = VILLE["rues"]
FEUX = set(VILLE["feux"])

# Historique dans SQLite (bouton Historique du client).
# Une ligne par simulation ; les temps sont en secondes. (Proposition de table pour serveur/base.py.)
FICHIER_BASE = Path(__file__).parent.parent / "donnees" / "simulations.db"
FICHIER_BASE.parent.mkdir(exist_ok=True)
BASE = sqlite3.connect(FICHIER_BASE)
BASE.execute("""CREATE TABLE IF NOT EXISTS simulations (
                    id INTEGER PRIMARY KEY, date TEXT, heure INTEGER, depart TEXT, arrivee TEXT,
                    classique REAL, trafic REAL, priorite REAL)""")


def enregistrer(demande, reponse):
    """Ajoute une simulation (une demande COMPUTE_ROUTE et sa réponse ROUTES) dans la base."""
    BASE.execute("INSERT INTO simulations (date, heure, depart, arrivee, classique, trafic, priorite) "
                 "VALUES (?, ?, ?, ?, ?, ?, ?)",
                 (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), demande["heure"], demande["depart"],
                  demande["arrivee"], reponse["classique"]["temps"], reponse["trafic"]["temps"],
                  reponse["priorite"]["temps"]))
    BASE.commit()                     # écrit vraiment dans le fichier

# Chaque route reçoit une "charge" de 0 à 1 (0 = toujours fluide, 1 = très chargée) :
# plus la route est près du centre-ville, plus elle est chargée.
CENTRE = (1700, 550)                       # vieille ville (Unterlinden, Petite Venise), en mètres
RAYON_CENTRE = 1300                        # au-delà de cette distance au centre : charge 0

VOISINS = {n: [] for n in NOEUDS}          # noeud -> [(voisin, longueur, charge), ...]
INFOS = {}                                 # (a, b) -> (longueur, charge), pour retrouver une route
for a, b, longueur in ROUTES:
    milieu = ((NOEUDS[a][0] + NOEUDS[b][0]) / 2, (NOEUDS[a][1] + NOEUDS[b][1]) / 2)
    charge = max(0, 1 - math.dist(milieu, CENTRE) / RAYON_CENTRE)
    VOISINS[a].append((b, longueur, charge))
    VOISINS[b].append((a, longueur, charge))
    INFOS[(a, b)] = INFOS[(b, a)] = (longueur, charge)


def feu_vert(feu, t):
    """Le feu est-il vert à l'instant t (en s depuis le départ du véhicule) ?

    Le cycle est décalé selon l'identifiant du feu, pour qu'ils ne changent pas tous ensemble.
    """
    return (t + int(feu)) % CYCLE_FEU < DUREE_VERT


def pic(heure):
    """Combien le trafic ralentit une route très chargée, selon l'heure."""
    if heure in (7, 8, 9, 17, 18, 19):
        return 2.0          # heures de pointe : jusqu'à 3 fois plus lent
    if 10 <= heure <= 16:
        return 1.0          # la journée : jusqu'à 2 fois plus lent
    return 0.0              # la nuit : tout est fluide


def temps_route(longueur, charge, heure):
    return longueur / VITESSE * (1 + charge * pic(heure))


def chemin_le_plus_court(depart, arrivee, cout):
    """Dijkstra : on agrandit petit à petit la zone des noeuds dont on connaît le coût.

    cout(voisin, longueur, charge) donne le "prix" d'une route : des mètres ou des secondes,
    selon la stratégie. C'est la seule chose qui change entre les 3 trajets.
    """
    total = {depart: 0}
    precedent = {depart: None}
    a_traiter = {depart}
    while a_traiter:
        noeud = min(a_traiter, key=lambda n: total[n])     # le moins cher pas encore traité
        a_traiter.remove(noeud)
        if noeud == arrivee:
            break
        for voisin, longueur, charge in VOISINS[noeud]:
            nouveau = total[noeud] + cout(voisin, longueur, charge)
            if voisin not in total or nouveau < total[voisin]:
                total[voisin] = nouveau
                precedent[voisin] = noeud
                a_traiter.add(voisin)
    if arrivee not in precedent:
        return None
    chemin = [arrivee]
    while chemin[-1] != depart:
        chemin.append(precedent[chemin[-1]])
    return chemin[::-1]


def mesurer(chemin, heure, respecte_feux):
    """Distance (m) et temps (s) réels d'un chemin, en comptant le trafic et les feux.

    respecte_feux : False pour le véhicule prioritaire (ses feux passent au vert).
    temps_noeuds : pour chaque noeud du chemin, [instant d'arrivée, instant de départ].
    Les deux sont égaux, sauf à un feu rouge : le véhicule y attend le vert.
    """
    distance = temps = 0
    temps_noeuds = [[0, 0]]
    for a, b in zip(chemin, chemin[1:]):
        longueur, charge = INFOS[(a, b)]
        distance += longueur
        temps += temps_route(longueur, charge, heure)
        arrivee = temps
        if respecte_feux and b in FEUX:
            while not feu_vert(b, temps):      # feu rouge : on attend le vert, seconde par seconde
                temps += 1
        temps_noeuds.append([round(arrivee, 1), round(temps, 1)])
    return {"chemin": chemin, "distance": round(distance, 1), "temps": round(temps, 1),
            "temps_noeuds": temps_noeuds}


def trois_trajets(depart, arrivee, heure):
    """Les 3 stratégies : seule la fonction de coût de Dijkstra change."""
    def cout_classique(voisin, longueur, charge):
        return longueur                        # des mètres : le plus court

    def cout_trafic(voisin, longueur, charge):
        if voisin in FEUX:
            return temps_route(longueur, charge, heure) + ATTENTE_FEU
        return temps_route(longueur, charge, heure)

    def cout_priorite(voisin, longueur, charge):
        return temps_route(longueur, charge, heure)   # le feu passe au vert : pas d'attente

    classique = chemin_le_plus_court(depart, arrivee, cout_classique)
    if classique is None:
        return None
    return {
        "type": "ROUTES",
        "classique": mesurer(classique, heure, True),
        "trafic": mesurer(chemin_le_plus_court(depart, arrivee, cout_trafic), heure, True),
        "priorite": mesurer(chemin_le_plus_court(depart, arrivee, cout_priorite), heure, False),
    }


def repondre(message):
    if message["type"] == "GET_CITY":
        return {"type": "CITY", "noeuds": NOEUDS, "routes": ROUTES, "lieux": LIEUX, "rues": RUES,
                "feux": VILLE["feux"]}
    if message["type"] == "GET_HISTORY":
        lignes = BASE.execute("SELECT heure, depart, arrivee, classique, trafic, priorite "
                              "FROM simulations ORDER BY id").fetchall()
        colonnes = ["heure", "depart", "arrivee", "classique", "trafic", "priorite"]
        return {"type": "HISTORY", "simulations": [dict(zip(colonnes, ligne)) for ligne in lignes]}
    if message["type"] == "GET_TRAFFIC":
        # densité de 0 (vide) à 1 (bouché) : la charge de la route x le pic de l'heure (max 2)
        heure = message["heure"]
        densites = [[a, b, round(INFOS[(a, b)][1] * pic(heure) / 2, 2)] for a, b, _ in ROUTES]
        return {"type": "TRAFFIC", "heure": heure, "densites": densites}
    if message["type"] == "COMPUTE_ROUTE":
        for nom in (message["depart"], message["arrivee"]):
            if nom not in NOEUDS:
                return {"type": "ERROR", "raison": f"noeud inconnu : {nom}"}
        reponse = trois_trajets(message["depart"], message["arrivee"], message["heure"])
        if reponse is None:
            return {"type": "ERROR", "raison": "aucun chemin entre ces deux points"}
        enregistrer(message, reponse)
        return reponse
    return {"type": "ERROR", "raison": f"type inconnu : {message['type']}"}


def repondre_carrefour(carrefours):
    """Un véhicule demande le feu vert (UDP) : le faux carrefour accorde toujours la priorité."""
    try:
        octets, vehicule = carrefours.recvfrom(4096)
        message = decoder(octets)
    except (OSError, ValueError):
        return                        # datagramme illisible (ou erreur Windows) : on l'ignore
    print("UDP reçu :", message)
    if message["type"] == "PRIORITY_REQUEST" and message.get("feu") in FEUX:
        reponse = {"type": "PRIORITY_GRANT", "feu": message["feu"]}
    else:
        reponse = {"type": "PRIORITY_DENY", "feu": message.get("feu"), "raison": "pas un feu connu"}
    carrefours.sendto(json.dumps(reponse).encode("utf-8"), vehicule)


def main():
    ecoute = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    if os.name != "nt":
        # Sous Linux : relancer tout de suite sans "Address already in use".
        # Pas sous Windows : là-bas, ça permettrait à DEUX serveurs d'écouter sur le même port.
        ecoute.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    ecoute.bind(("0.0.0.0", PORT_TCP))
    ecoute.listen()
    carrefours = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)   # UDP : les carrefours (étape 7)
    carrefours.bind(("0.0.0.0", PORT_UDP))
    print(f"Faux serveur en écoute : TCP {PORT_TCP}, UDP {PORT_UDP} (Ctrl+C pour arrêter)")
    clients = {}                      # socket -> Deframeur
    while True:
        lisibles, _, _ = select.select([ecoute, carrefours, *clients], [], [], 0.5)
        for s in lisibles:
            if s is carrefours:
                repondre_carrefour(carrefours)
                continue
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
            except (OSError, ValueError, KeyError) as e:     # KeyError : champ manquant
                print("déconnexion :", e)
                del clients[s]
                s.close()


if __name__ == "__main__":
    main()
