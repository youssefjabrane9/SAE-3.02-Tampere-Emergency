"""Protocole réseau commun au client (poste du régulateur) et au serveur (centre de régulation).

CE FICHIER EST LE CONTRAT ENTRE LES DEUX MOITIÉS DU PROJET.
Personne ne le modifie seul : tout changement passe par une pull request relue par l'autre.

Règles de transport
-------------------
TCP (PORT_TCP) : client <-> serveur.
    Une trame = un objet JSON (un dict) encodé en UTF-8, suivi de '\\n'.
    Pourquoi le '\\n' ? TCP est un flux d'octets : un recv() peut renvoyer
    un demi-message, ou deux messages collés. Le '\\n' marque la fin de chaque message.

UDP (PORT_UDP) : véhicule (OBU) <-> carrefour connecté (RSU), à partir de l'étape 7.
    Un datagramme = un objet JSON. Pas besoin de '\\n' : UDP garde les frontières des messages.

Tout message est un dict qui contient au moins la clé "type".
"""

import json

PORT_TCP = 5050
PORT_UDP = 5051


# ---------------------------------------------------------------------------
# Catalogue des messages (un exemple réel par message).
# Si vous ajoutez un champ, ajoutez-le ici D'ABORD, puis dans le code.
# ---------------------------------------------------------------------------

# Étape 4-5 : la carte et un itinéraire --------------------------------------

EXEMPLE_GET_CITY = {"type": "GET_CITY"}                          # client -> serveur

EXEMPLE_CITY = {                                                  # serveur -> client
    "type": "CITY",
    "noeuds": {"A1": [0, 0], "A2": [0, 100], "B1": [100, 0], "B2": [100, 100]},  # nom -> [x, y] en mètres
    "routes": [["A1", "A2", 100], ["A1", "B1", 100], ["A2", "B2", 100], ["B1", "B2", 100]],  # [départ, arrivée, longueur]
}

EXEMPLE_COMPUTE_ROUTE = {                                         # client -> serveur
    "type": "COMPUTE_ROUTE",
    "depart": "A1",
    "arrivee": "B2",
    "heure": 8,              # 0 à 23, utilisé à partir de l'étape 6
}

EXEMPLE_ROUTE = {                                                 # serveur -> client
    "type": "ROUTE",
    "chemin": ["A1", "A2", "B2"],
    "distance": 200,         # mètres
    "temps": 24.0,           # secondes estimées
}

EXEMPLE_ERROR = {"type": "ERROR", "raison": "noeud inconnu : Z9"}  # serveur -> client

# Étape 6 : vous remplacerez sans doute ROUTE par ROUTES (3 stratégies), par exemple :
#   {"type": "ROUTES", "classique": {...}, "trafic": {...}, "priorite": {...}}

# Étape 7 (UDP) : à compléter ensemble quand vous y serez, par exemple :
#   PRIORITY_REQUEST (véhicule -> carrefour), PRIORITY_GRANT / PRIORITY_DENY (carrefour -> véhicule)

TYPES_CONNUS = {"GET_CITY", "CITY", "COMPUTE_ROUTE", "ROUTE", "ERROR"}


# ---------------------------------------------------------------------------
# Fonctions à écrire vous-mêmes. Les tests de test_protocole.py disent quand c'est bon.
# ---------------------------------------------------------------------------

def encoder(message):
    """dict -> octets prêts à envoyer en TCP (JSON + '\\n', en UTF-8).

    Indice : json.dumps(...), puis ajouter "\\n", puis .encode("utf-8").
    """
    return (json.dumps(message) + "\n").encode("utf-8")


def decoder(ligne):
    """octets d'UNE trame (sans le '\\n') -> dict.

    Doit lever ValueError si ce n'est pas un dict ou s'il n'y a pas de clé "type".
    Indice : .decode("utf-8"), puis json.loads(...), puis vérifier.
    """
    message = json.loads(ligne.decode("utf-8"))
    if not isinstance(message, dict) or "type" not in message:
        raise ValueError("message invalide : il faut un dict avec une clé \"type\"")
    return message


class Deframeur:
    """Reconstitue les messages à partir de morceaux reçus par recv().

    Utilisation (côté client comme côté serveur, un Deframeur par connexion) :
        d = Deframeur()
        for msg in d.alimenter(sock.recv(4096)):
            traiter(msg)
    """

    def __init__(self):
        self.tampon = b""

    def alimenter(self, octets):
        """Ajoute les octets reçus au tampon et renvoie la liste des messages COMPLETS.

        Ce qui reste après le dernier '\\n' (un message pas encore fini) reste dans le tampon
        pour le prochain appel.
        Indice : tant que b"\\n" est dans le tampon, couper avec .split(b"\\n", 1).
        """
        self.tampon += octets
        messages = []
        while b"\n" in self.tampon:
            ligne, self.tampon = self.tampon.split(b"\n", 1)
            messages.append(decoder(ligne))
        return messages
