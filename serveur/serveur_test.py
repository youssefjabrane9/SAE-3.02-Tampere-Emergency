
import json
import math
import socket
import sqlite3
import heapq
import threading
from datetime import datetime
from pathlib import Path

from commun.protocole import PORT_TCP, PORT_UDP, Deframeur, decoder, encoder

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


# Charge de chaque route, de 0 (toujours fluide) a 1 (tres chargee) :
# plus la route est pres du centre-ville, plus elle est chargee.
CENTRE = (1700, 550)        # vieille ville (Unterlinden, Petite Venise), en metres
RAYON_CENTRE = 1300         # au-dela de cette distance du centre : charge 0


def charge_route(a, b):
    xa, ya = ville["noeuds"][a]
    xb, yb = ville["noeuds"][b]
    milieu = ((xa + xb) / 2, (ya + yb) / 2)
    return max(0, 1 - math.dist(milieu, CENTRE) / RAYON_CENTRE)


# Sens uniques : la carte est decoupee au bord de Colmar, donc certains carrefours
# sont des impasses (on peut y entrer sans pouvoir en ressortir, ou l'inverse).
# On garde le "coeur" de la ville : les carrefours d'ou l'on peut aller partout
# ET revenir. Un depart ou une arrivee hors du coeur est remplace par le carrefour
# du coeur le plus proche.
def atteignables(depart, voisins):
    vus = {depart}
    a_voir = [depart]

    while a_voir:
        noeud = a_voir.pop()

        for voisin in voisins.get(noeud, []):
            if voisin not in vus:
                vus.add(voisin)
                a_voir.append(voisin)

    return vus


def calculer_coeur():
    # Le meme graphe, mais avec toutes les routes a l'envers
    inverse = {}

    for a, liste in graphe.items():
        for b, longueur in liste:
            inverse.setdefault(b, []).append(a)

    suivants = {a: [b for b, longueur in liste] for a, liste in graphe.items()}

    for noeud in ville["noeuds"]:
        # aller partout depuis noeud ET revenir jusqu'a noeud
        coeur = atteignables(noeud, suivants) & atteignables(noeud, inverse)

        if len(coeur) > len(ville["noeuds"]) / 2:
            return coeur

    return set(ville["noeuds"])


coeur = calculer_coeur()


def carrefour_du_coeur(noeud):
    if noeud in coeur:
        return noeud

    x, y = ville["noeuds"][noeud]
    return min(
        coeur,
        key=lambda n: math.dist((x, y), ville["noeuds"][n])
    )


# Niveau de trafic selon l'heure
def niveau_trafic(heure):
    if 7 <= heure <= 9 or 17 <= heure <= 19:
        return "fort"

    if 10 <= heure <= 16:
        return "moyen"

    return "faible"


# Ralentissement maximal (sur une route de charge 1) selon l'heure
def ralentissement(heure):
    if niveau_trafic(heure) == "fort":
        return 1        # jusqu'a 2 fois plus lent
    if niveau_trafic(heure) == "moyen":
        return 0.4      # jusqu'a 1,4 fois plus lent
    return 0


# Calculer le temps sur une route.
# Le trafic et les feux comptent pour TOUS les vehicules, classique compris :
# le classique choisit seulement son chemin sans en tenir compte (le plus court en metres).
def temps_route(a, b, longueur, heure, strategie):
    temps = longueur / 10

    # Routes chargees : plus lentes pres du centre-ville
    temps *= 1 + charge_route(a, b) * ralentissement(heure)

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


# Attente a un feu, selon la strategie (les memes valeurs que dans temps_route)
def attente_feu(b, strategie):
    if b not in feux:
        return 0

    if strategie == "prioritaire":
        return 3

    return 20


# Pour l'animation du client : [arrivee, depart] en secondes a chaque noeud du chemin.
# Les deux sont differents seulement a un feu, ou le vehicule attend.
def temps_aux_noeuds(chemin, heure, strategie):
    t = 0
    resultat = [[0, 0]]

    for a, b in zip(chemin, chemin[1:]):
        longueur = next(
            l for voisin, l in graphe[a] if voisin == b
        )

        t += temps_route(a, b, longueur, heure, strategie)
        arrivee = t - attente_feu(b, strategie)
        resultat.append([round(arrivee, 1), round(t, 1)])

    return resultat


# Densite du trafic de chaque route (0 = fluide, 1 = bouche), pour colorer la carte.
# Meme regle que temps_route : la charge de la route x le ralentissement de l'heure.
def densites_trafic(heure):
    densites = []

    for a, b, longueur in ville["routes"]:
        densite = charge_route(a, b) * ralentissement(heure)
        densites.append([a, b, round(densite, 2)])

    return densites


# Historique des simulations dans une base SQLite (donnees/simulations.db).
# Une connexion par appel : chaque client a son propre thread.
FICHIER_BASE = Path(__file__).resolve().parent.parent / "donnees" / "simulations.db"
FICHIER_BASE.parent.mkdir(exist_ok=True)


def ouvrir_base():
    base = sqlite3.connect(FICHIER_BASE)
    base.execute("""CREATE TABLE IF NOT EXISTS simulations (
                        id INTEGER PRIMARY KEY, date TEXT, heure INTEGER,
                        depart TEXT, arrivee TEXT,
                        classique REAL, trafic REAL, priorite REAL)""")
    return base


def enregistrer(heure, depart, arrivee, reponse):
    base = ouvrir_base()
    base.execute(
        "INSERT INTO simulations (date, heure, depart, arrivee, classique, trafic, priorite) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), heure, depart, arrivee,
         reponse["classique"]["temps"], reponse["trafic"]["temps"], reponse["priorite"]["temps"])
    )
    base.commit()
    base.close()


def lire_historique():
    base = ouvrir_base()
    lignes = base.execute(
        "SELECT heure, depart, arrivee, classique, trafic, priorite FROM simulations ORDER BY id"
    ).fetchall()
    base.close()
    colonnes = ["heure", "depart", "arrivee", "classique", "trafic", "priorite"]
    return [dict(zip(colonnes, ligne)) for ligne in lignes]


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
            "rues": ville["rues"],
            "feux": ville["feux"]
        }

    if message.get("type") == "GET_TRAFFIC":
        try:
            heure = int(message.get("heure", 8))
        except (ValueError, TypeError):
            heure = 8

        return {
            "type": "TRAFFIC",
            "heure": heure,
            "densites": densites_trafic(heure)
        }

    if message.get("type") == "GET_HISTORY":
        return {
            "type": "HISTORY",
            "simulations": lire_historique()
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

        # Hors du coeur de la ville : on part du carrefour le plus proche
        resultats = calculer_strategies(
            carrefour_du_coeur(depart), carrefour_du_coeur(arrivee), heure
        )

        if any(r is None for r in resultats.values()):
            return {
                "type": "ERROR",
                "raison": "Aucun trajet trouve"
            }

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

        # Le client attend "priorite" (et pas "prioritaire") et, pour
        # chaque trajet, "temps_noeuds" pour animer les vehicules
        noms_client = {
            "classique": "classique",
            "trafic": "trafic",
            "prioritaire": "priorite"
        }
        reponse = {"type": "ROUTES"}

        for nom, resultat in resultats.items():
            resultat["temps_noeuds"] = temps_aux_noeuds(
                resultat["chemin"], heure, nom
            )
            reponse[noms_client[nom]] = resultat

        enregistrer(heure, depart, arrivee, reponse)

        return reponse

    return {
        "type": "ERROR",
        "raison": "Commande non disponible"
    }


# Carrefours connectes (UDP) : le vehicule prioritaire demande le feu vert
def lancer_carrefours():
    carrefours = socket.socket(
        socket.AF_INET,
        socket.SOCK_DGRAM
    )

    carrefours.bind(("0.0.0.0", PORT_UDP))
    print("Carrefours en ecoute sur le port UDP", PORT_UDP)

    while True:
        try:
            donnees, vehicule = carrefours.recvfrom(4096)
            message = decoder(donnees)
        except (OSError, ValueError):
            continue

        feu = message.get("feu")

        if message.get("type") == "PRIORITY_REQUEST" and feu in feux:
            reponse = {"type": "PRIORITY_GRANT", "feu": feu}
        else:
            reponse = {"type": "PRIORITY_DENY", "feu": feu}

        print("Priorite demandee pour le feu", feu, ":", reponse["type"])
        carrefours.sendto(
            json.dumps(reponse).encode("utf-8"),
            vehicule
        )


# Dialogue avec UN client, dans son propre thread
def gerer_client(client):
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

    # 0.0.0.0 : accepte les clients des autres machines (la VM client)
    serveur.bind(("0.0.0.0", PORT_TCP))
    serveur.listen()

    print("Serveur demarre sur le port", PORT_TCP)
    print("Carte de Colmar chargee")
    print("Trois strategies disponibles")

    # Les carrefours tournent dans un thread a part, en meme temps que le TCP
    threading.Thread(target=lancer_carrefours, daemon=True).start()

    try:
        while True:
            client, adresse = serveur.accept()
            print("Client connecte :", adresse)

            # Un thread par client : plusieurs clients peuvent etre connectes en meme temps
            threading.Thread(
                target=gerer_client, args=(client,), daemon=True
            ).start()

    except KeyboardInterrupt:
        print("Arret du serveur")

    finally:
        serveur.close()


if __name__ == "__main__":
    lancer_serveur()
