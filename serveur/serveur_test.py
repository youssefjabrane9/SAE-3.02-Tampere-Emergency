
import json
import socket
import heapq
from pathlib import Path

from sae.protocole import Deframeur, encoder

# Charger la carte de Colmar
fichier = Path(__file__).resolve().parent.parent / "assets" / "colmar.json"

with open(fichier, "r", encoding="utf-8") as f:
    ville = json.load(f)

# Construire le graphe des routes
graphe = {}
sens_uniques = {(a, b) for a, b in ville["sens_uniques"]}
feux = set(ville["feux"])

for a, b, longueur in ville["routes"]:
    graphe.setdefault(a, []).append((b, longueur))

    if (a, b) not in sens_uniques:
        graphe.setdefault(b, []).append((a, longueur))


# Niveau de trafic selon l'heure
def niveau_trafic(heure):
    if 7 <= heure <= 9 or 17 <= heure <= 19:
        return "fort"

    if 10 <= heure <= 16:
        return "moyen"

    return "faible"


# Calculer le temps sur une route
def temps_route(a, b, longueur, heure, strategie):
    temps = longueur / 10

    if strategie == "classique":
        return temps

    # Simulation de routes chargees
    route_chargee = (int(a) + int(b)) % 3 == 0

    if route_chargee:
        if niveau_trafic(heure) == "fort":
            temps *= 2
        elif niveau_trafic(heure) == "moyen":
            temps *= 1.4

    # Attente aux feux
    if b in feux:
        if strategie == "prioritaire":
            temps += 3
        else:
            temps += 20

    return temps


# Algorithme de Dijkstra
def dijkstra(depart, arrivee, heure, strategie):
    couts = {depart: 0}
    precedents = {}
    file = [(0, depart)]

    while file:
        cout, noeud = heapq.heappop(file)

        if cout > couts.get(noeud, float("inf")):
            continue

        if noeud == arrivee:
            break

        for voisin, longueur in graphe.get(noeud, []):
            if strategie == "classique":
                poids = longueur
            else:
                poids = temps_route(
                    noeud, voisin, longueur, heure, strategie
                )

            nouveau = cout + poids

            if nouveau < couts.get(voisin, float("inf")):
                couts[voisin] = nouveau
                precedents[voisin] = noeud
                heapq.heappush(file, (nouveau, voisin))

    if arrivee not in couts:
        return None

    chemin = [arrivee]

    while chemin[-1] != depart:
        chemin.append(precedents[chemin[-1]])

    chemin.reverse()

    distance = 0
    temps = 0

    for a, b in zip(chemin, chemin[1:]):
        longueur = next(
            l for voisin, l in graphe[a] if voisin == b
        )

        distance += longueur
        temps += temps_route(
            a, b, longueur, heure, strategie
        )

    return {
        "chemin": chemin,
        "distance": round(distance, 1),
        "temps": round(temps, 1)
    }


# Calculer les trois strategies
def calculer_strategies(depart, arrivee, heure):
    resultats = {}

    for nom in ("classique", "trafic", "prioritaire"):
        resultats[nom] = dijkstra(
            depart, arrivee, heure, nom
        )

    return resultats


# Traiter les messages du client
def traiter_message(message):

    if message.get("type") == "GET_CITY":
        return {
            "type": "CITY",
            "noeuds": ville["noeuds"],
            "routes": ville["routes"],
            "lieux": ville["lieux"],
            "rues": ville["rues"]
        }

    if message.get("type") == "COMPUTE_ROUTE":
        depart = message.get("depart")
        arrivee = message.get("arrivee")

        try:
            heure = int(message.get("heure", 8))
        except (ValueError, TypeError):
            heure = -1

        if depart not in ville["noeuds"] or arrivee not in ville["noeuds"]:
            return {
                "type": "ERROR",
                "raison": "Depart ou arrivee inconnu"
            }

        if not 0 <= heure <= 23:
            return {
                "type": "ERROR",
                "raison": "Heure invalide"
            }

        resultats = calculer_strategies(
            depart, arrivee, heure
        )

        if any(r is None for r in resultats.values()):
            return {
                "type": "ERROR",
                "raison": "Aucun trajet trouve"
            }

        classique = resultats["classique"]

        print("Trajets calcules pour", heure, "h")

        for nom, resultat in resultats.items():
            print(
                nom,
                ":",
                resultat["distance"],
                "m,",
                resultat["temps"],
                "s"
            )

        return {
            "type": "ROUTE",
            "chemin": classique["chemin"],
            "distance": classique["distance"],
            "temps": classique["temps"],
            "strategies": resultats,
            "trafic": niveau_trafic(heure)
        }

    return {
        "type": "ERROR",
        "raison": "Commande non disponible"
    }


# Demarrer le serveur TCP
def lancer_serveur():
    serveur = socket.socket(
        socket.AF_INET,
        socket.SOCK_STREAM
    )

    serveur.setsockopt(
        socket.SOL_SOCKET,
        socket.SO_REUSEADDR,
        1
    )

    serveur.bind(("127.0.0.1", 5050))
    serveur.listen()

    print("Serveur demarre sur le port 5050")
    print("Carte de Colmar chargee")
    print("Trois strategies disponibles")

    try:
        while True:
            client, adresse = serveur.accept()
            print("Client connecte :", adresse)

            deframeur = Deframeur()

            try:
                while True:
                    donnees = client.recv(4096)

                    if not donnees:
                        break

                    for message in deframeur.alimenter(donnees):
                        reponse = traiter_message(message)
                        client.sendall(encoder(reponse))

            except (OSError, ValueError, KeyError) as erreur:
                print("Erreur client :", erreur)

            finally:
                client.close()
                print("Client deconnecte")

    except KeyboardInterrupt:
        print("Arret du serveur")

    finally:
        serveur.close()


if __name__ == "__main__":
    lancer_serveur()
