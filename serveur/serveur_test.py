
import json
import socket
import heapq
from pathlib import Path

from sae.protocole import Deframeur, encoder


# 1. Charger les donnees de Colmar
fichier = Path(__file__).resolve().parent.parent / "assets" / "colmar.json"

with open(fichier, "r", encoding="utf-8") as f:
    ville = json.load(f)


# 2. Construire le graphe des routes
# en respectant les sens uniques

graphe = {}

sens_uniques = {
    (depart, arrivee)
    for depart, arrivee in ville["sens_uniques"]
}

for depart, arrivee, distance in ville["routes"]:

    # Ajouter le sens indique dans les donnees
    graphe.setdefault(depart, []).append((arrivee, distance))

    # Ajouter le sens inverse uniquement si la route
    # n'est pas declaree a sens unique
    if (depart, arrivee) not in sens_uniques:
        graphe.setdefault(arrivee, []).append((depart, distance))


# 3. Algorithme de Dijkstra
def dijkstra(depart, arrivee):

    distances = {depart: 0}
    precedents = {}
    file = [(0, depart)]

    while file:

        distance, noeud = heapq.heappop(file)

        if distance > distances.get(noeud, float("inf")):
            continue

        if noeud == arrivee:
            break

        for voisin, longueur in graphe.get(noeud, []):

            nouvelle_distance = distance + longueur

            if nouvelle_distance < distances.get(voisin, float("inf")):

                distances[voisin] = nouvelle_distance
                precedents[voisin] = noeud

                heapq.heappush(
                    file,
                    (nouvelle_distance, voisin)
                )

    if arrivee not in distances:
        return None

    chemin = [arrivee]

    while chemin[-1] != depart:
        chemin.append(precedents[chemin[-1]])

    chemin.reverse()

    return distances[arrivee], chemin


# 4. Creer le serveur TCP
serveur = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

serveur.setsockopt(
    socket.SOL_SOCKET,
    socket.SO_REUSEADDR,
    1
)

serveur.bind(("127.0.0.1", 5050))

serveur.listen()

print("Serveur demarre sur le port 5050")
print("Carte de Colmar chargee")
print("Gestion des sens uniques active")


# 5. Communication avec le client
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

                    print("Message recu :", message["type"])

                    # Envoyer la carte de Colmar
                    if message["type"] == "GET_CITY":

                        reponse = {
                            "type": "CITY",
                            "noeuds": ville["noeuds"],
                            "routes": ville["routes"],
                            "lieux": ville["lieux"],
                            "rues": ville["rues"]
                        }

                    # Calculer un itineraire
                    elif message["type"] == "COMPUTE_ROUTE":

                        depart = message["depart"]
                        arrivee = message["arrivee"]

                        resultat = dijkstra(depart, arrivee)

                        if resultat is None:

                            reponse = {
                                "type": "ERROR",
                                "raison": "Aucun trajet trouve"
                            }

                        else:

                            distance, chemin = resultat

                            reponse = {
                                "type": "ROUTE",
                                "chemin": chemin,
                                "distance": round(distance, 1),
                                "temps": round(distance / 10, 1)
                            }

                            print(
                                "Trajet calcule :",
                                round(distance, 1),
                                "m"
                            )

                    else:

                        reponse = {
                            "type": "ERROR",
                            "raison": "Commande non disponible"
                        }

                    client.sendall(encoder(reponse))

        finally:

            client.close()
            print("Client deconnecte")

except KeyboardInterrupt:

    print("Arret du serveur")

finally:

    serveur.close()
