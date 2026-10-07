"""FAUX serveur, uniquement pour tester le client tant que serveur/serveur.py (Youssef) n'existe pas.

    python -m outils.faux_serveur

Ville 3 x 3 (A1 à C3, 100 m entre deux carrefours). Le trajet est un simple parcours en
largeur (le moins de carrefours), pas le vrai calcul de Youssef. Plusieurs clients possibles.
"""

import select
import socket

from sae.protocole import PORT_TCP, Deframeur, encoder

COLONNES = "ABC"
LIGNES = range(1, 4)
ECART = 100          # mètres entre deux carrefours
VITESSE = 13.9       # m/s (50 km/h)

NOEUDS = {f"{c}{l}": [i * ECART, (l - 1) * ECART] for i, c in enumerate(COLONNES) for l in LIGNES}
ROUTES = ([[f"{c}{l}", f"{c}{l + 1}", ECART] for c in COLONNES for l in LIGNES if l < len(LIGNES)]
          + [[f"{a}{l}", f"{b}{l}", ECART] for a, b in zip(COLONNES, COLONNES[1:]) for l in LIGNES])


def chemin_le_plus_court(depart, arrivee):
    voisins = {nom: [] for nom in NOEUDS}
    for a, b, _ in ROUTES:
        voisins[a].append(b)
        voisins[b].append(a)
    precedent = {depart: None}
    a_visiter = [depart]
    while a_visiter:
        noeud = a_visiter.pop(0)
        for v in voisins[noeud]:
            if v not in precedent:
                precedent[v] = noeud
                a_visiter.append(v)
    chemin = [arrivee]
    while chemin[-1] != depart:
        chemin.append(precedent[chemin[-1]])
    return chemin[::-1]


def repondre(message):
    if message["type"] == "GET_CITY":
        return {"type": "CITY", "noeuds": NOEUDS, "routes": ROUTES}
    if message["type"] == "COMPUTE_ROUTE":
        for nom in (message["depart"], message["arrivee"]):
            if nom not in NOEUDS:
                return {"type": "ERROR", "raison": f"noeud inconnu : {nom}"}
        chemin = chemin_le_plus_court(message["depart"], message["arrivee"])
        distance = (len(chemin) - 1) * ECART
        return {"type": "ROUTE", "chemin": chemin, "distance": distance,
                "temps": round(distance / VITESSE, 1)}
    return {"type": "ERROR", "raison": f"type inconnu : {message['type']}"}


def main():
    ecoute = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
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
